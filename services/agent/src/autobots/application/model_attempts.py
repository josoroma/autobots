"""One bounded model call: classify failures, retry only what is safe, run no partial output."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from autobots.application.model_admission import (
    AdmissionRequest,
    ModelAdmission,
    SettlementReason,
    Ticket,
)

MAX_RETRIES = 2
BACKOFF_SECONDS = (1.0, 2.0)
# Longer isn't waited out. A worker runs one job at a time, and a cancel isn't seen while asleep.
MAX_RETRY_WAIT_SECONDS = 60.0


class FailureClass(StrEnum):
    CREDENTIALS_REQUIRED = "credentials_required"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    # Nothing answers on a local route's port: the owner's server isn't running (Decision 0041 A3).
    LOCAL_MODEL_SERVER_UNAVAILABLE = "local_model_server_unavailable"
    COST_UNAVAILABLE = "cost_unavailable"
    INVALID_CREDENTIAL = "invalid_credential"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    RATE_LIMITED = "rate_limited"
    PROVIDER_ERROR = "provider_error"
    NETWORK_BEFORE_ACCEPTANCE = "network_before_acceptance"
    PARTIAL_STREAM = "partial_stream"
    UNCERTAIN_ACCEPTANCE = "uncertain_acceptance"
    INCOMPLETE_OUTPUT = "incomplete_output"
    OTHER = "other"


RETRYABLE = frozenset(
    {FailureClass.RATE_LIMITED, FailureClass.PROVIDER_ERROR, FailureClass.NETWORK_BEFORE_ACCEPTANCE}
)
# The request may have been accepted, so its cost and effects stay unknown until reconciled.
UNCERTAIN = frozenset({FailureClass.PARTIAL_STREAM, FailureClass.UNCERTAIN_ACCEPTANCE})


class ProviderFailure(Exception):
    def __init__(
        self,
        failure: FailureClass,
        *,
        retry_after: float | None = None,
        accumulated_output: str = "",
        reason: str | None = None,
    ) -> None:
        super().__init__(failure.value)
        self.failure = failure
        self.retry_after = retry_after
        self.accumulated_output = accumulated_output
        # Which path ended a call that raised nothing of its own, for the log.
        self.reason = reason


def classify_status(status: int) -> FailureClass:
    """MP-08's table. Anything unexplained is not retried, and only a refusal frees a reservation.

    A success the SDK couldn't parse, or a timeout at the edge, may still have been charged.
    """
    if status < 400 or status in {408, 504, 524}:
        return FailureClass.UNCERTAIN_ACCEPTANCE
    if status == 401:
        return FailureClass.INVALID_CREDENTIAL
    if status == 402:
        return FailureClass.INSUFFICIENT_CREDITS
    if status == 404:
        return FailureClass.MODEL_UNAVAILABLE
    if status == 429:
        return FailureClass.RATE_LIMITED
    return FailureClass.PROVIDER_ERROR if 500 <= status < 600 else FailureClass.OTHER


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelOutput:
    """A finished response. `complete` is false on truncation, and its tool calls never run."""

    text: str
    complete: bool
    tool_calls: tuple[ToolCall, ...] = ()
    charged_micro_usd: int | None = None
    upstream_provider: str | None = None


def executable_tool_calls(output: ModelOutput) -> tuple[ToolCall, ...]:
    """A streamed prefix or truncated response is progress, never executable arguments."""
    if not output.complete:
        raise ProviderFailure(FailureClass.INCOMPLETE_OUTPUT)
    return output.tool_calls


@dataclass(frozen=True)
class RetryPolicy:
    """The root deadline bounds each wait, and a wait past it stops the retries."""

    deadline: datetime
    sleep: Callable[[float], Awaitable[None]]
    now: Callable[[], datetime] = field(default=lambda: datetime.now(UTC))


async def call_with_policy(
    admission: ModelAdmission,
    request: AdmissionRequest,
    dispatch: Callable[[Ticket], Awaitable[ModelOutput]],
    policy: RetryPolicy,
    *,
    is_cancelled: Callable[[], bool] = lambda: False,
) -> ModelOutput:
    """Each attempt is its own recorded row against the same budget, model and deadline."""
    attempt = request.attempt
    retries = 0
    while True:
        if is_cancelled():
            raise ProviderFailure(FailureClass.OTHER)
        ticket = await admission.admit(_with_attempt(request, attempt))
        await admission.mark_dispatched(ticket.invocation_id)
        try:
            output = await dispatch(ticket)
        except ProviderFailure as failure:
            if failure.failure in UNCERTAIN:
                await admission.mark_uncertain(
                    ticket.invocation_id, failure.failure.value, failure.accumulated_output
                )
                raise
            await admission.fail_before_acceptance(ticket.invocation_id, failure.failure.value)
            delay = max(failure.retry_after or 0.0, BACKOFF_SECONDS[min(retries, 1)])
            allowed = failure.failure in RETRYABLE and retries < MAX_RETRIES
            if (
                not allowed
                or delay > MAX_RETRY_WAIT_SECONDS
                or policy.now() + timedelta(seconds=delay) > policy.deadline
                or is_cancelled()
            ):
                raise
            retries += 1
            attempt += 1
            await policy.sleep(delay)
            continue
        if output.charged_micro_usd is None:
            # The call worked, and the provider reported no charge, so the estimate stays open.
            await admission.mark_uncertain(
                ticket.invocation_id, SettlementReason.CHARGE_NOT_REPORTED.value, output.text
            )
        else:
            await admission.settle(
                ticket.invocation_id,
                output.charged_micro_usd,
                upstream_provider=output.upstream_provider,
            )
        return output


def _with_attempt(request: AdmissionRequest, attempt: int) -> AdmissionRequest:
    return replace(request, attempt=attempt)
