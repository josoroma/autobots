"""`LoopMiddleware` through its public methods. Its guard and admission ledger are in-memory
stand-ins passed through its seams, and every other step is its own (PTST-01). The disposable
checks drive it over real rows (tests/db/goal_loop_check.py, memory_check.py and
admission_check.py)."""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from datetime import datetime
from typing import Any, cast
from uuid import UUID, uuid4

import httpx
import openrouter
import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolCall, ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolRuntime

from autobots.adapters.loop_middleware import (
    MAX_FACT_CHARS,
    MAX_FACT_NAMES,
    LoopMiddleware,
    reply_facts,
)
from autobots.application.compaction import CompactionPolicy
from autobots.application.loop_admission import current_middleware
from autobots.application.loop_policy import REPAIR_NOTE, LoopStopped, uncertain_call_fields
from autobots.application.model_admission import (
    AdmissionRefused,
    AdmissionRequest,
    AttemptAlreadySettled,
    BudgetExceeded,
    ModelAdmission,
    NoInferenceSlot,
    ReplyFacts,
    Ticket,
)
from autobots.application.model_attempts import FailureClass, ProviderFailure, classify_status
from autobots.application.run_usage import COUNTER_SQL, RootLimits
from autobots.application.sql import SqlParams
from autobots.application.tool_definitions import ToolScope
from autobots.contracts.plans import GoalSpec
from autobots.domain.models import ModelRoute
from autobots.logs import JsonFormatter, redact
from fake_openrouter import DEEPSEEK, TERRA, invoke, model_over
from sql_fakes import ScriptedConnection

SCOPE = ToolScope(uuid4(), uuid4(), 1, {})
ROUTE = ModelRoute("executor", TERRA.id.value, TERRA.wire_id, 1_000)
SUMMARY_ROUTE = ModelRoute("summarizer", DEEPSEEK.id.value, DEEPSEEK.wire_id, 500)
GOAL = GoalSpec(
    objective="Write the report",
    original_request="Write the report",
    criteria={"c1": "the report exists"},
    allowed_tools={},
    allowed_paths=[],
)
# Three 150-character turns pass it, and the last one stays in view beside the summary.
TIGHT = CompactionPolicy(context_chars=200, keep_recent=1)


class Usage:
    """One run's `app_private.run_usage` row, as `consume` and the middleware read it, and the
    summaries stored. Nothing else is stored: no earlier summary, open wait or pending approval, and
    no run or lease, so the default guard finds no run."""

    def __init__(self) -> None:
        self.used = dict.fromkeys(COUNTER_SQL, 0)
        self.consumed: list[str] = []
        self.summaries: list[str] = []
        self._row: tuple[object, ...] | None = None

    # Each answer is a tuple, read by position.
    description = None

    async def execute(self, statement: str, params: SqlParams | None = None, /) -> "Usage":
        values = tuple(params) if isinstance(params, Sequence) else ()
        self._row = None
        for counter, sql in COUNTER_SQL.items():
            if statement == sql:
                self.consumed.append(counter)
                limit = values[1]
                assert isinstance(limit, int)
                if self.used[counter] < limit:
                    self.used[counter] += 1
                    self._row = (self.used[counter],)
                return self
        if statement.startswith("select model_calls from app_private.run_usage"):
            self._row = (self.used["model_calls"],)
        elif statement.startswith("insert into app_private.run_summaries"):
            self.summaries.append(str(values[3]))
        return self

    async def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    async def fetchall(self) -> list[tuple[object, ...]]:
        return []

    @contextlib.asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield


class Ledger(ModelAdmission):
    """Admission in memory. `admit` records each request, then raises the arranged refusals in
    order, as the real ledger refuses a busy slot or a spent budget, and then reserves."""

    def __init__(self, *refusals: AdmissionRefused) -> None:
        super().__init__(connection=ScriptedConnection())
        self.refusals = list(refusals)
        self.asked: list[AdmissionRequest] = []
        self.events: list[tuple[str, object]] = []

    def admitted_roles(self) -> list[object]:
        return [detail for event, detail in self.events if event == "admitted"]

    async def admit(self, request: AdmissionRequest, *, at: datetime | None = None) -> Ticket:
        self.asked.append(request)
        if self.refusals:
            raise self.refusals.pop(0)
        self.events.append(("admitted", request.role))
        return Ticket(uuid4(), request.worst_case_micro_usd, False, 1, 1)

    async def mark_dispatched(self, invocation_id: UUID) -> None:
        self.events.append(("dispatched", None))

    async def settle(
        self, invocation_id: UUID, charged_micro_usd: int, *, upstream_provider: str | None = None
    ) -> None:
        self.events.append(("settled", charged_micro_usd))

    async def fail_before_acceptance(self, invocation_id: UUID, failure_class: str) -> None:
        self.events.append(("failed", failure_class))

    async def mark_uncertain(
        self, invocation_id: UUID, failure_class: str, accumulated_output: str = ""
    ) -> None:
        self.events.append(("uncertain", failure_class))

    async def reconcile(
        self, invocation_id: UUID, charged_micro_usd: int, source: str = "owner"
    ) -> None:
        self.events.append(("reconciled", charged_micro_usd))

    async def record_reply(self, invocation_id: UUID, facts: ReplyFacts) -> None:
        self.events.append(("reply", facts.finish_reason))


def request(messages: list[AnyMessage]) -> ModelRequest[Any]:
    """The SDK's model request, holding only what the middleware reads and overrides."""
    return ModelRequest(model=GenericFakeChatModel(messages=iter([])), messages=messages)


class Model:
    """The SDK's model handler: each request gets the next reply, and is recorded."""

    def __init__(self, *replies: AIMessage) -> None:
        self.replies = list(replies)
        self.requests: list[ModelRequest[Any]] = []

    async def __call__(self, request: ModelRequest[Any]) -> ModelResponse[Any]:
        self.requests.append(request)
        return ModelResponse(result=[self.replies.pop(0)])


def reply(text: str = "done", finish: str = "stop") -> AIMessage:
    return AIMessage(content=text, response_metadata={"finish_reason": finish, "cost": 0.0001})


def history() -> ModelRequest[Any]:
    """More than TIGHT holds, so the first two turns are summarized before the call."""
    return request([HumanMessage("a" * 150), AIMessage("b" * 150), HumanMessage("c" * 150)])


def loop(
    usage: Usage,
    ledger: Ledger,
    waits: list[float] | None = None,
    *,
    limits: RootLimits | None = None,
    goal: GoalSpec | None = None,
) -> LoopMiddleware:
    """The real middleware over `usage`, with `ledger` admitting and a guard that always passes."""

    async def owned() -> float:
        return 60.0

    async def sleep(seconds: float) -> None:
        if waits is not None:
            waits.append(seconds)

    return LoopMiddleware(
        usage,
        SCOPE,
        limits or RootLimits(),
        ROUTE,
        sleep=sleep,
        goal=goal,
        compaction=TIGHT,
        summary_route=SUMMARY_ROUTE,
        guard=owned,
        admission=lambda: ledger,
    )


def test_a_refused_summary_stops_the_loop_with_its_reason() -> None:
    """A budget that runs out during compaction pauses the run like one at any other call."""
    usage, ledger, model = Usage(), Ledger(BudgetExceeded("arranged")), Model()
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(loop(usage, ledger, goal=GOAL).awrap_model_call(history(), model))
    assert caught.value.code == "budget_exceeded"
    assert [asked.role for asked in ledger.asked] == ["summarizer"]
    assert model.requests == [] and usage.summaries == []


def test_a_busy_slot_during_a_summary_is_waited_out_like_any_other_call() -> None:
    usage, waits = Usage(), list[float]()
    ledger = Ledger(NoInferenceSlot("arranged"), NoInferenceSlot("arranged"))
    model = Model(reply("ARRANGED-SUMMARY"), reply("the answer"))
    middleware = loop(usage, ledger, waits, goal=GOAL)
    response = asyncio.run(middleware.awrap_model_call(history(), model))
    assert waits == [1.0, 1.0]
    assert [asked.role for asked in ledger.asked] == ["summarizer"] * 3 + ["executor"]
    assert usage.summaries == ["ARRANGED-SUMMARY"]
    assert response.result[-1].content == "the answer"
    # The answer is asked with the summary in place of the two turns it covers.
    sent = model.requests[1].messages
    assert len(sent) == 3 and "ARRANGED-SUMMARY" in str(sent[1].content)


@pytest.mark.parametrize(
    ("finish", "repairs"), [("length", 1), ("error", 0), ("content_filter", 0)]
)
def test_only_a_cut_off_reply_is_worth_a_repair(finish: str, repairs: int) -> None:
    usage, model = Usage(), Model(reply("", finish))
    middleware = loop(usage, Ledger(), limits=RootLimits(repairs=0))
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.awrap_model_call(request([HumanMessage("hello")]), model))
    assert caught.value.code == "incomplete_output"
    assert usage.consumed.count("repairs") == repairs


def test_a_cut_off_reply_is_asked_once_more_briefly() -> None:
    usage, ledger = Usage(), Ledger()
    model = Model(reply("", "length"), reply("short"))
    response = asyncio.run(
        loop(usage, ledger).awrap_model_call(request([HumanMessage("hello")]), model)
    )
    assert response.result[-1].content == "short"
    assert model.requests[1].messages[-1].content == REPAIR_NOTE
    assert usage.used["repairs"] == 1
    assert ledger.admitted_roles() == ["executor", "executor"]


def test_running_out_of_model_calls_while_compacting_stops_cleanly() -> None:
    """The summary's call counts against the run's limit. Past it, nothing is sent, and its
    reservation closes as never accepted."""
    usage, ledger, model = Usage(), Ledger(), Model()
    middleware = loop(usage, ledger, limits=RootLimits(model_calls=0), goal=GOAL)
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.awrap_model_call(history(), model))
    assert caught.value.code == "model_calls_limit"
    assert model.requests == []
    assert ledger.events[-1] == ("failed", "other")


def test_an_unencodable_request_stops_before_anything_is_reserved() -> None:
    """A lone surrogate is no text a provider can read."""
    usage, ledger, model = Usage(), Ledger(), Model()
    unencodable = request([HumanMessage(b"before \\ud83d after".decode("unicode_escape"))])
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(loop(usage, ledger).admitted(unencodable, model, ROUTE))
    assert caught.value.code == "request_unencodable"
    assert ledger.asked == [] and model.requests == []


def test_without_a_guard_each_dispatch_reads_the_runs_ownership() -> None:
    """The default guard is the database's: a run it doesn't hold stops before any admission."""
    ledger = Ledger()
    middleware = LoopMiddleware(Usage(), SCOPE, RootLimits(), ROUTE, admission=lambda: ledger)
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.admitted(request([HumanMessage("hello")]), Model(), ROUTE))
    assert caught.value.code == "run_not_found"
    assert ledger.asked == []


class SettledMeanwhile(Ledger):
    """Recovery settled the attempt while it was out, so settling it here is refused, or `error`
    is raised there instead."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error

    async def settle(
        self, invocation_id: UUID, charged_micro_usd: int, *, upstream_provider: str | None = None
    ) -> None:
        raise self.error


def test_an_attempt_recovery_settled_stops_as_lost_and_keeps_its_late_charge() -> None:
    """The charge the reply reported is late evidence for the attempt recovery classified."""
    ledger = SettledMeanwhile(AttemptAlreadySettled("this attempt has already been settled"))
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(
            loop(Usage(), ledger).admitted(request([HumanMessage("hello")]), Model(reply()), ROUTE)
        )
    assert caught.value.code == "lease_lost"
    assert ledger.events[-1] == ("reconciled", 100)


def test_any_other_value_error_while_settling_is_a_defect_not_a_lost_lease() -> None:
    """Only the ledger's own refusal means recovery got there first (refactor plan R-41,
    PADP-11)."""
    ledger = SettledMeanwhile(ValueError("arranged defect"))
    with pytest.raises(ValueError, match="arranged defect"):
        asyncio.run(
            loop(Usage(), ledger).admitted(request([HumanMessage("hello")]), Model(reply()), ROUTE)
        )
    assert ("reconciled", 100) not in ledger.events


# What a reply or a failed call leaves in the ledger and the log, split from
# test_worker_inference.py by module (PTST-04)


def test_a_success_the_sdk_cant_parse_keeps_its_reservation() -> None:
    """A reply arrived, so it may have been charged. A 200 is not a refusal."""

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 500, "message": "arranged"}})

    with pytest.raises(openrouter.errors.ResponseValidationError) as caught:
        invoke(model_over(handle))
    assert classify_status(caught.value.status_code) is FailureClass.UNCERTAIN_ACCEPTANCE


def _logged(error: BaseException) -> str:
    record = logging.LogRecord("autobots.worker", logging.WARNING, "", 0, "e", (), None)
    record.fields = uncertain_call_fields(error)
    return JsonFormatter().format(record)


def test_an_uncertain_calls_log_names_types_and_status_and_no_reply_text() -> None:
    """The reply's text really is in the exception, so its absence from the log means something."""
    text = "arranged-reply-text-7f3a"

    def handle(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": 500, "message": text}})

    with pytest.raises(openrouter.errors.ResponseValidationError) as caught:
        invoke(model_over(handle))
    # In what the exception holds, its body. Its `str()` embeds a shortened validation error.
    assert text in repr(caught.value)
    assert redact(text) == text
    line = json.loads(_logged(caught.value))
    assert line["status"] == 200
    assert line["error_type"].endswith(".ResponseValidationError")
    assert line["cause_type"].endswith("ValidationError")
    assert text not in json.dumps(line)


def test_an_exceptions_cause_is_named_and_neither_message_is_kept() -> None:
    sentinel = "arranged-sentinel-91c2"
    try:
        try:
            raise ValueError(sentinel)
        except ValueError as cause:
            raise RuntimeError(sentinel) from cause
    except RuntimeError as error:
        assert sentinel in str(error) and sentinel in str(error.__cause__)
        assert redact(sentinel) == sentinel
        written = _logged(error)
    line = json.loads(written)
    assert line["error_type"] == "builtins.RuntimeError"
    assert line["cause_type"] == "builtins.ValueError"
    assert "status" not in line
    assert sentinel not in written


def test_an_exception_raised_while_handling_another_names_that_one() -> None:
    try:
        try:
            raise ValueError("arranged")
        except ValueError:
            raise RuntimeError("arranged")  # noqa: B904
    except RuntimeError as error:
        assert uncertain_call_fields(error)["cause_type"] == "builtins.ValueError"


def test_a_cause_set_outside_any_handler_is_named() -> None:
    # `__context__` is empty here, so reading only that would lose the cause.
    error = RuntimeError("arranged")
    error.__cause__ = ValueError("arranged")
    assert error.__context__ is None
    assert uncertain_call_fields(error)["cause_type"] == "builtins.ValueError"


def test_a_status_that_is_no_number_isnt_reported_as_one() -> None:
    class Odd(Exception):
        status_code = "504"

    assert uncertain_call_fields(Odd("arranged")).get("status") is None


def test_a_partial_streams_output_stays_out_of_its_fields() -> None:
    sentinel = "arranged-partial-44d1"
    fields = uncertain_call_fields(
        ProviderFailure(FailureClass.PARTIAL_STREAM, accumulated_output=sentinel)
    )
    assert fields == {"error_type": "autobots.application.model_attempts.ProviderFailure"}


def test_reply_facts_hold_no_content_and_stay_bounded() -> None:
    calls = [
        {"name": "x" * 500, "args": {"content": "the report's text"}, "id": str(number)}
        for number in range(30)
    ]
    message = AIMessage(
        content="the report's text",
        tool_calls=calls,
        invalid_tool_calls=[{"name": "save_artifact", "args": '{"pa', "id": "cut", "error": "bad"}],
        response_metadata={"finish_reason": "length"},
        usage_metadata={
            "input_tokens": 9,
            "output_tokens": 512,
            "total_tokens": 521,
            "output_token_details": {"reasoning": 400},
        },
    )
    facts = reply_facts(message)
    assert (
        facts.finish_reason,
        facts.input_tokens,
        facts.output_tokens,
        facts.reasoning_tokens,
    ) == ("length", 9, 512, 400)
    assert facts.invalid_tool_calls == 1
    assert len(facts.tool_names) == MAX_FACT_NAMES and {len(name) for name in facts.tool_names} == {
        MAX_FACT_CHARS
    }
    assert "report" not in repr(facts)
    # A reply with nothing to report is still a record, not a failure.
    empty = reply_facts(AIMessage(content=""))
    assert (
        empty.finish_reason,
        empty.output_tokens,
        empty.tool_names,
        empty.invalid_tool_calls,
    ) == (None, None, (), 0)


# The tool-call path: a dispatch is counted, and the gateway's code, which GatewayMiddleware puts in
# the reply's artifact, stops the loop or spends a repair (PADP-16).


def tool_request() -> ToolCallRequest:
    call = ToolCall(name="save_note", args={}, id="call-1", type="tool_call")
    # The middleware reads only the call; the runtime is the graph's, absent outside one.
    return ToolCallRequest(tool_call=call, tool=None, state={}, runtime=cast(ToolRuntime, None))


def answered(code: str | None) -> Callable[[ToolCallRequest], Awaitable[ToolMessage]]:
    async def gateway(_: ToolCallRequest) -> ToolMessage:
        return ToolMessage(
            content="{}", artifact={"outcome": "failed", "code": code}, tool_call_id="call-1"
        )

    return gateway


@pytest.mark.parametrize(
    ("code", "stops", "repairs"),
    [(None, None, 0), ("lease_lost", "lease_lost", 0), ("invalid_arguments", None, 1)],
)
def test_the_gateways_code_decides_whether_the_loop_goes_on(
    code: str | None, stops: str | None, repairs: int
) -> None:
    usage = Usage()
    middleware = loop(usage, Ledger())
    if stops is None:
        reply = asyncio.run(middleware.awrap_tool_call(tool_request(), answered(code)))
        assert reply.artifact["code"] == code
    else:
        with pytest.raises(LoopStopped) as caught:
            asyncio.run(middleware.awrap_tool_call(tool_request(), answered(code)))
        assert caught.value.code == stops
    assert usage.consumed.count("tool_dispatches") == 1
    assert usage.consumed.count("repairs") == repairs


def test_a_tool_call_past_the_dispatch_limit_never_reaches_the_gateway() -> None:
    async def never(_: ToolCallRequest) -> ToolMessage:
        raise AssertionError("dispatched past the limit")

    middleware = loop(Usage(), Ledger(), limits=RootLimits(tool_dispatches=0))
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.awrap_tool_call(tool_request(), never))
    assert caught.value.code == "tool_dispatches_limit"


def test_a_stop_a_tools_own_model_call_met_stops_the_loop_after_it() -> None:
    """Browsing's model calls go through this loop's admission; a stop there ends the loop too."""
    ledger = Ledger(BudgetExceeded("arranged"))
    middleware = loop(Usage(), ledger)

    async def browsing(_: ToolCallRequest) -> ToolMessage:
        nested = current_middleware()
        assert nested is middleware
        with pytest.raises(LoopStopped):
            await nested.admitted(request([HumanMessage("step")]), Model(reply()), ROUTE)
        return await answered(None)(tool_request())

    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.awrap_tool_call(tool_request(), browsing))
    assert caught.value.code == "budget_exceeded"


def test_a_guard_that_refuses_at_dispatch_closes_the_reservation_as_never_sent() -> None:
    """A stop met after admission, before sending, is the loop's stop, not the failure class."""
    checks: list[int] = []

    async def owned_once() -> float:
        checks.append(1)
        if len(checks) > 1:
            raise LoopStopped("run_not_running")
        return 60.0

    ledger, model = Ledger(), Model(reply())
    middleware = LoopMiddleware(
        Usage(), SCOPE, RootLimits(), ROUTE, guard=owned_once, admission=lambda: ledger
    )
    with pytest.raises(LoopStopped) as caught:
        asyncio.run(middleware.admitted(request([HumanMessage("hello")]), model, ROUTE))
    assert caught.value.code == "run_not_running"
    assert ledger.events[-1] == ("failed", "other") and model.requests == []
