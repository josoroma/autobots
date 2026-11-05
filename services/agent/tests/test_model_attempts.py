"""Failure classes and retries on an in-memory ledger. Real rows run in scripts/app_db.py."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import httpx
import openrouter
import pytest
from pydantic import SecretStr

from autobots.adapters.models.catalog import CatalogEntry, CatalogSnapshot
from autobots.adapters.models.factory import chat_model, default_sdk_client, prepare_attempt
from autobots.application.model_admission import (
    AdmissionRequest,
    CostUnavailable,
    Pricing,
    Ticket,
    worst_case_cost,
)
from autobots.application.model_attempts import (
    MAX_RETRIES,
    FailureClass,
    ModelOutput,
    ProviderFailure,
    RetryPolicy,
    ToolCall,
    call_with_policy,
    classify_status,
    executable_tool_calls,
)
from autobots.domain.models import PROFILES, ModelProfileId, ModelRole, resolve_role_policy
from fake_openrouter import ARRANGED_KEY

NOW = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
GOOD = ModelOutput("done", True, charged_micro_usd=10, upstream_provider="fixture")


class Ledger:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []
        self.requests: list[AdmissionRequest] = []

    async def admit(self, request: AdmissionRequest, *, at: datetime | None = None) -> Ticket:
        self.requests.append(request)
        self.events.append(("admit", request.attempt))
        return Ticket(uuid4(), request.worst_case_micro_usd, False, 1, 1)

    async def mark_dispatched(self, _invocation: UUID) -> None:
        self.events.append(("dispatched", None))

    async def settle(
        self, _invocation: UUID, charged: int, *, upstream_provider: str | None
    ) -> None:
        self.events.append(("settled", charged))

    async def fail_before_acceptance(self, _invocation: UUID, failure: str) -> None:
        self.events.append(("failed", failure))

    async def mark_uncertain(self, _invocation: UUID, failure: str, output: str = "") -> None:
        self.events.append(("uncertain", (failure, output)))


def request() -> AdmissionRequest:
    return AdmissionRequest(uuid4(), uuid4(), uuid4(), "coder", "openrouter_terra", "w", 1, 5)


def policy(deadline_seconds: float = 900) -> tuple[RetryPolicy, list[float]]:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    return RetryPolicy(NOW + timedelta(seconds=deadline_seconds), sleep, now=lambda: NOW), waits


def scripted(*steps: Any) -> Any:
    remaining = list(steps)

    async def dispatch(_ticket: Ticket) -> ModelOutput:
        step = remaining.pop(0)
        if isinstance(step, Exception):
            raise step
        output: ModelOutput = step
        return output

    return dispatch


def run_call(ledger: Ledger, dispatch: Any, retry: RetryPolicy, **options: Any) -> Any:
    return call_with_policy(ledger, request(), dispatch, retry, **options)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, FailureClass.INVALID_CREDENTIAL),
        (402, FailureClass.INSUFFICIENT_CREDITS),
        (429, FailureClass.RATE_LIMITED),
        (500, FailureClass.PROVIDER_ERROR),
        (503, FailureClass.PROVIDER_ERROR),
        (400, FailureClass.OTHER),
        (404, FailureClass.MODEL_UNAVAILABLE),
        (200, FailureClass.UNCERTAIN_ACCEPTANCE),
        (408, FailureClass.UNCERTAIN_ACCEPTANCE),
        (504, FailureClass.UNCERTAIN_ACCEPTANCE),
        (524, FailureClass.UNCERTAIN_ACCEPTANCE),
    ],
)
def test_status_classes(status: int, expected: FailureClass) -> None:
    assert classify_status(status) is expected


@pytest.mark.asyncio
async def test_a_retry_respects_retry_after_and_stays_recorded() -> None:
    ledger, (retry, waits) = Ledger(), policy()
    failure = ProviderFailure(FailureClass.RATE_LIMITED, retry_after=7.0)
    assert await run_call(ledger, scripted(failure, GOOD), retry) is GOOD
    assert waits == [7.0]
    assert [e for e in ledger.events if e[0] in {"admit", "failed", "settled"}] == [
        ("admit", 1),
        ("failed", "rate_limited"),
        ("admit", 2),
        ("settled", 10),
    ]
    assert {r.wire_id for r in ledger.requests} == {"w"}, "the same model"


@pytest.mark.asyncio
async def test_at_most_two_retries() -> None:
    ledger, (retry, waits) = Ledger(), policy()
    failures = [ProviderFailure(FailureClass.PROVIDER_ERROR) for _ in range(5)]
    with pytest.raises(ProviderFailure):
        await run_call(ledger, scripted(*failures), retry)
    assert len(ledger.requests) == MAX_RETRIES + 1
    assert len(waits) == MAX_RETRIES


@pytest.mark.asyncio
async def test_a_wait_past_the_cap_is_not_slept_through() -> None:
    ledger, (retry, waits) = Ledger(), policy(deadline_seconds=900)
    failure = ProviderFailure(FailureClass.RATE_LIMITED, retry_after=61.0)
    with pytest.raises(ProviderFailure):
        await run_call(ledger, scripted(failure, GOOD), retry)
    assert waits == []
    assert len(ledger.requests) == 1


@pytest.mark.asyncio
async def test_the_root_deadline_stops_a_retry() -> None:
    ledger, (retry, waits) = Ledger(), policy(deadline_seconds=5)
    failure = ProviderFailure(FailureClass.RATE_LIMITED, retry_after=60.0)
    with pytest.raises(ProviderFailure):
        await run_call(ledger, scripted(failure, GOOD), retry)
    assert waits == []
    assert len(ledger.requests) == 1


@pytest.mark.parametrize(
    "failure",
    [FailureClass.INVALID_CREDENTIAL, FailureClass.INSUFFICIENT_CREDITS, FailureClass.OTHER],
)
@pytest.mark.asyncio
async def test_unsafe_failures_are_never_retried(failure: FailureClass) -> None:
    ledger, (retry, waits) = Ledger(), policy()
    with pytest.raises(ProviderFailure):
        await run_call(ledger, scripted(ProviderFailure(failure), GOOD), retry)
    assert len(ledger.requests) == 1 and waits == []


@pytest.mark.parametrize(
    "failure", [FailureClass.PARTIAL_STREAM, FailureClass.UNCERTAIN_ACCEPTANCE]
)
@pytest.mark.asyncio
async def test_uncertain_outcomes_keep_the_record_and_never_redispatch(
    failure: FailureClass,
) -> None:
    ledger, (retry, waits) = Ledger(), policy()
    uncertain = ProviderFailure(failure, accumulated_output="partial")
    with pytest.raises(ProviderFailure):
        await run_call(ledger, scripted(uncertain, GOOD), retry)
    assert len(ledger.requests) == 1 and waits == []
    assert ("uncertain", (failure.value, "partial")) in ledger.events
    assert not any(event[0] in {"failed", "settled"} for event in ledger.events)


@pytest.mark.asyncio
async def test_a_missing_reported_charge_is_not_invented() -> None:
    ledger, (retry, _) = Ledger(), policy()
    await run_call(ledger, scripted(ModelOutput("done", True)), retry)
    assert ("uncertain", ("charge_not_reported", "done")) in ledger.events


@pytest.mark.asyncio
async def test_cancellation_stops_a_retry() -> None:
    ledger, (retry, _) = Ledger(), policy()
    failure = ProviderFailure(FailureClass.RATE_LIMITED)
    with pytest.raises(ProviderFailure):
        await run_call(
            ledger, scripted(failure, GOOD), retry, is_cancelled=lambda: bool(ledger.requests)
        )
    assert len(ledger.requests) == 1


def test_incomplete_output_never_runs_tools() -> None:
    call = ToolCall("write_file", {"path": "x"})
    with pytest.raises(ProviderFailure) as caught:
        executable_tool_calls(ModelOutput("", False, (call,)))
    assert caught.value.failure is FailureClass.INCOMPLETE_OUTPUT
    assert executable_tool_calls(ModelOutput("", True, (call,))) == (call,)


def test_worst_case_cost_rounds_up_and_needs_a_price() -> None:
    pricing = Pricing(input_per_million=1_000_000, output_per_million=2_000_000, per_request=3)
    assert worst_case_cost(pricing, 8000, 512) == 8000 + 1024 + 3
    assert worst_case_cost(Pricing(1, 1), 1, 0) == 1
    with pytest.raises(CostUnavailable):
        worst_case_cost(None, 1, 1)
    with pytest.raises(CostUnavailable):
        worst_case_cost(Pricing(-1, 1), 1, 1)


def model_over(handler: Any) -> Any:
    profile = PROFILES[ModelProfileId.DEEPSEEK_FLASH]
    catalog = CatalogSnapshot(
        "fixture", NOW, (CatalogEntry(profile.wire_id, profile.canonical_id, frozenset()),)
    )
    attempt = prepare_attempt(resolve_role_policy(), ModelRole.CODER, catalog, now=NOW)

    def factory(key: str) -> openrouter.OpenRouter:
        return default_sdk_client(key, http=httpx.Client(transport=httpx.MockTransport(handler)))

    return chat_model(attempt, SecretStr(ARRANGED_KEY), client_factory=factory)


@pytest.mark.parametrize("status", [401, 402, 429, 500, 502, 503])
def test_the_real_adapter_surfaces_each_status_without_retrying(status: int) -> None:
    """The SDK's own default retries 5XX for up to an hour, so each status must reach us once."""
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(status, json={"error": {"code": status, "message": "arranged"}})

    with pytest.raises(openrouter.errors.OpenRouterError) as caught:
        model_over(handle).invoke("hello")
    assert caught.value.status_code == status
    assert len(calls) == 1


def test_a_connection_error_is_not_retried_by_the_sdk() -> None:
    calls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        raise httpx.ConnectError("arranged")

    with pytest.raises(httpx.TransportError):
        model_over(handle).invoke("hello")
    assert len(calls) == 1


def test_the_default_client_has_sdk_retries_off() -> None:
    profile = PROFILES[ModelProfileId.DEEPSEEK_FLASH]
    catalog = CatalogSnapshot(
        "fixture", NOW, (CatalogEntry(profile.wire_id, profile.canonical_id, frozenset()),)
    )
    attempt = prepare_attempt(resolve_role_policy(), ModelRole.CODER, catalog, now=NOW)
    model = chat_model(attempt, SecretStr(ARRANGED_KEY))
    assert model.client.sdk_configuration.retry_config.strategy == "none"
