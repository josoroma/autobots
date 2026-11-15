"""What US-11.12's independent review found, held in place. Fakes only, and no model call."""

import asyncio
import io
import json
import logging
import logging.config
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import pytest
import uvicorn
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from autobots.adapters.loop_middleware import request_bytes
from autobots.adapters.models.catalog import RESERVED_PROMPT_TOKENS, parse_pricing
from autobots.application.assignments import narrowed_tools
from autobots.application.backups import restore_history
from autobots.application.loop_policy import past_known_price, reservation_for
from autobots.application.model_attempts import FailureClass, ProviderFailure
from autobots.application.operations import REQUIRED_COLUMNS, database_conditions
from autobots.application.sql import SqlParams
from autobots.application.tool_definitions import ToolFailed
from autobots.application.worker_inference import AttemptModel, CatalogCache, InferenceSource
from autobots.contracts.run_commands import RunRequest
from autobots.domain.models import ModelRole, ModelRoute, resolve_role_policy
from autobots.domain.tools import DELEGATION_TOOL
from autobots.logs import JsonFormatter, configure_logging
from autobots.operations.worker import inference_step
from fake_openrouter import catalog_payload, provider_context
from sql_fakes import ScriptedRows

ROUTE = ModelRoute("executor", "openrouter_terra", "fixture/model", 34_560, 1_000_000)


class Lookup(BaseModel):
    """A tool's schema, which goes in the request too."""

    item: str


def test_a_request_under_the_assumed_size_keeps_the_routes_reservation() -> None:
    assert reservation_for(ROUTE, RESERVED_PROMPT_TOKENS) == 34_560
    assert reservation_for(ROUTE, 10) == 34_560


def test_a_larger_request_reserves_for_every_byte_past_it() -> None:
    assert reservation_for(ROUTE, RESERVED_PROMPT_TOKENS + 1000) == 34_560 + 1000


def test_with_no_known_rate_the_reservation_stays_the_routes() -> None:
    route = ModelRoute("executor", "openrouter_terra", "fixture/model", 34_560)
    assert reservation_for(route, RESERVED_PROMPT_TOKENS * 2) == 34_560


def test_the_size_counts_the_system_prompt_and_tool_schemas() -> None:
    """Compaction counts neither, and instructions plus skills can be very large."""
    base = SimpleNamespace(messages=[HumanMessage("hi")], system_message=None, tools=[])
    long_prompt = SimpleNamespace(
        messages=[HumanMessage("hi")], system_message=SystemMessage("x" * 50_000), tools=[]
    )
    tools = SimpleNamespace(messages=[HumanMessage("hi")], system_message=None, tools=[Lookup])
    assert request_bytes(long_prompt) >= request_bytes(base) + 50_000
    assert request_bytes(tools) > request_bytes(base)


def test_a_price_above_the_reservation_is_refused_before_sending() -> None:
    async def catalog() -> dict[str, Any]:
        return catalog_payload(pricing={"prompt": "0.001", "completion": "0.001"})

    source = InferenceSource("postgresql://never", provider_context(), CatalogCache(catalog))
    policy = resolve_role_policy()
    assert ModelRole.EXECUTOR in policy.bindings
    with pytest.raises(ProviderFailure) as refused:
        asyncio.run(source.open_attempt(uuid4(), policy, reserved_micro_usd=34_560))
    assert refused.value.failure is FailureClass.COST_UNAVAILABLE


def test_uvicorns_own_loggers_go_through_the_redacting_format() -> None:
    # What uvicorn itself installs before the app loads: without the fix, this keeps its handler.
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    server = logging.getLogger("uvicorn.error")
    assert logging.getLogger("uvicorn").handlers != []
    stream = io.StringIO()
    configure_logging(stream)
    assert logging.getLogger("uvicorn").handlers == []
    assert logging.getLogger("uvicorn").propagate is True
    assert server.propagate is True
    # The access logger's own check, which decides whether a line is logged at all.
    assert logging.getLogger("uvicorn.access").hasHandlers() is False
    try:
        raise RuntimeError("postgresql://user:hunter2@host/db")
    except RuntimeError:
        server.exception("Exception in ASGI application")
    line = stream.getvalue()
    assert "hunter2" not in line
    assert json.loads(line.splitlines()[-1])["error"] == "RuntimeError"
    assert isinstance(logging.getLogger().handlers[0].formatter, JsonFormatter)


def test_a_bad_restore_line_is_skipped_and_the_rest_read(tmp_path: Path) -> None:
    good = {
        "at": "2026-11-06T12:00:00+00:00",
        "result": "passed",
        "checks_passed": 1,
        "checks_total": 1,
    }
    folder = tmp_path / "a"
    folder.mkdir()
    (folder / "restores.jsonl").write_text(
        "not json\n" + json.dumps({"at": "x", "extra": True}) + "\n[1]\n" + json.dumps(good) + "\n"
    )
    binary = tmp_path / "b"
    binary.mkdir()
    (binary / "restores.jsonl").write_bytes(b"\xff\xfe")
    assert restore_history(str(tmp_path)) == [good]


class FakeConnection:
    def __init__(self, missing_columns: int) -> None:
        self.missing_columns = missing_columns

    async def execute(self, statement: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        if "pg_attribute" in statement:
            return ScriptedRows([(self.missing_columns,)])
        if "installation_holds" in statement:
            return ScriptedRows([()])
        return ScriptedRows([(0,)])

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield

    async def __aenter__(self) -> "FakeConnection":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self._connection = connection

    def connection(self) -> FakeConnection:
        return self._connection


def test_a_missing_column_reads_as_schema_behind() -> None:
    """A column-only migration used to leave Operations reading ready on a stale database."""
    conditions = asyncio.run(database_conditions(FakePool(FakeConnection(1))))
    assert conditions[1].code == "schema_behind"
    assert REQUIRED_COLUMNS


def test_a_network_error_reading_usage_isnt_reported_as_a_figure() -> None:
    from autobots.operations.reasoning_trial import key_usage

    def client() -> httpx.AsyncClient:
        def fail(_: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route")

        return httpx.AsyncClient(base_url="https://x.invalid", transport=httpx.MockTransport(fail))

    from pydantic import SecretStr

    assert asyncio.run(key_usage(SecretStr("sk-or-arranged"), client)) is None


def test_a_usage_reply_that_isnt_json_isnt_reported_as_a_figure() -> None:
    from pydantic import SecretStr

    from autobots.operations.reasoning_trial import key_usage

    def client() -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url="https://x.invalid",
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="<html>")),
        )

    assert asyncio.run(key_usage(SecretStr("sk-or-arranged"), client)) is None


def test_each_attempt_passes_its_reservation_on() -> None:
    """Without this wiring, a fresh price is never compared with what was reserved."""
    seen: list[int | None] = []

    class Source:
        async def open_attempt(
            self, _: Any, __: Any, reserved_micro_usd: int | None = None, **___: Any
        ) -> Any:
            seen.append(reserved_micro_usd)
            raise ProviderFailure(FailureClass.COST_UNAVAILABLE)

    model = AttemptModel(Source(), uuid4(), resolve_role_policy(), reserved_micro_usd=77)  # type: ignore[arg-type]
    with pytest.raises(ProviderFailure):
        asyncio.run(model.bind_tools([]).ainvoke([]))
    assert seen == [77]


def test_after_a_stop_the_step_claims_nothing() -> None:
    stop = asyncio.Event()
    stop.set()
    step = inference_step(SimpleNamespace(), None, None, stop)  # type: ignore[arg-type]
    # A claim would read the unset configuration and raise. It returns having done nothing.
    assert asyncio.run(step(None)) is False  # type: ignore[arg-type]


def test_asking_for_delegation_the_parent_cant_give_is_refused() -> None:
    with pytest.raises(ToolFailed):
        narrowed_tools({"calculate": 1}, {"calculate": 1}, [DELEGATION_TOOL], 1, 2)
    assert DELEGATION_TOOL not in narrowed_tools(
        {"calculate": 1, DELEGATION_TOOL: 1}, {"calculate": 1}, ["calculate"], 1, 2
    )


def test_a_goal_can_be_left_out_only_when_continuing() -> None:
    assert RunRequest.model_validate({"continues_run_id": str(uuid4())}).goal_text is None
    with pytest.raises(ValueError, match="goal_text"):
        RunRequest.model_validate({"limit_micro_usd": 1})


def test_a_rate_above_the_assumed_size_is_kept_as_where_refusals_start() -> None:
    item = {
        "pricing": {
            "prompt": "0.000001",
            "completion": "0.000002",
            "overrides": [{"min_prompt_tokens": 272_000, "prompt": "0.01", "completion": "0.01"}],
        }
    }
    pricing = parse_pricing(item)
    assert pricing is not None
    assert pricing.tier_from_tokens == 272_000
    route = ModelRoute("executor", "p", "w", 1_000, 1_000_000, pricing.tier_from_tokens)
    assert past_known_price(route, 272_000)
    assert not past_known_price(route, 271_999)
    assert not past_known_price(ROUTE, 10_000_000)


def test_a_request_counts_its_real_bytes() -> None:
    text = "\u6f22" * 1_000
    request = SimpleNamespace(messages=[HumanMessage(text)], system_message=None, tools=[])
    # Three bytes each in UTF-8, where an escaped form would count six.
    assert 3_000 <= request_bytes(request) < 4_000


def test_a_lone_surrogate_is_refused_before_any_reservation() -> None:
    request = SimpleNamespace(
        messages=[HumanMessage(b"before \\ud83d after".decode("unicode_escape"))],
        system_message=None,
        tools=[],
    )
    # The middleware stops on it before reserving (tests/test_loop_middleware.py).
    with pytest.raises(UnicodeEncodeError):
        request_bytes(request)


def test_a_tools_real_bytes_count_too() -> None:
    def tool(description: str) -> SimpleNamespace:
        return SimpleNamespace(
            messages=[],
            system_message=None,
            tools=[{"type": "function", "function": {"description": description}}],
        )

    # Three bytes each in UTF-8, where an escaped form would count six.
    assert request_bytes(tool("\u6f22" * 100)) - request_bytes(tool("")) == 300
