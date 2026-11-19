"""POST /v1/runs in process: each of its nine admission steps, branch by branch, and which refusal
wins when several apply (refactor plan R-31, PAPI-02 and PAPI-15).

Admission's collaborators are faked where they meet the outside: the database answers scripted rows,
membership and the key check are fakes, and the start-up environment is a fixture. Binding
resolution, tool availability, MP-01's policy order and `runs.admit` run for real. No socket,
database or model is used.

The steps, in order: (1) an Expert needs a session; (2) a budget or a limit, and a budget within
Decision 0022 D11's rules and today's cap; (3) a usable OpenRouter key; (4) only an owner pins an
Expert version (Decision 0011 M8), asked before admission opens its connection; (5) the workspace's
saved policy is read; (6) the session's routing resolves; (7) no granted tool is unavailable
(PRD-Tool-Catalog PK-02); (8) every resolved profile is offered (PRD-Model-Providers MP-01); (9) the
run is admitted under its idempotency key.
"""

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from itertools import combinations
from typing import Any
from uuid import UUID

import pytest

from autobots.api.dependencies import model_key_check, require_ready
from autobots.api.errors import ApiError
from autobots.api.resources import resources_of
from fake_api import MEMBER, OWNER, WORKSPACE, ApiClient
from fake_openrouter import provider_context

SESSION = UUID("0b000000-0000-4000-8000-000000000051")
EXPERT = UUID("0b000000-0000-4000-8000-0000000000e1")
ANOTHER_EXPERT = UUID("0b000000-0000-4000-8000-0000000000e2")
EARLIER = UUID("0b000000-0000-4000-8000-0000000000f1")
REPLAYED = UUID("0b000000-0000-4000-8000-0000000000f2")
# What the entry point read at start. It names no Tavily key, whatever the live environment holds.
STARTUP = {"AUTOBOTS_FIXTURE": "read at start"}
GOAL: dict[str, object] = {"goal_text": "Write the report"}
THROUGH_SESSION: dict[str, object] = {
    **GOAL,
    "session_id": str(SESSION),
    "expert_id": str(EXPERT),
}
KEY_NEEDED = "Model-backed work needs a usable OpenRouter key."
ROUTING = "That routing isn't available."
TOOL_MISSING = (
    "A tool this Expert grants is unavailable in this install. See Tools for what it needs."
)
DEEPSEEK = "DeepSeek isn't offered for new runs until it's qualified."


class KeyCheck:
    """`ProviderSettings.run_intent` as admission reads it: the arranged answer, logged."""

    def __init__(self, code: str, log: list[str]) -> None:
        self.code = code
        self.log = log

    async def run_intent(self, workspace_id: UUID) -> str:
        assert workspace_id == WORKSPACE
        self.log.append("run_intent")
        return self.code


@dataclass
class Arranged:
    """One request, and what admission's collaborators answer. As given, it is admitted."""

    user: UUID = OWNER
    body: dict[str, object] = field(default_factory=lambda: dict(THROUGH_SESSION))
    key: str = "ready"
    daily_cap: int | None = None
    spent_today: int = 0
    saved_policy: tuple[str | None, dict[str, str]] | None = None
    session: tuple[str, list[dict[str, object]]] | None = (
        "direct",
        [{"expert_id": str(EXPERT), "version": 1}],
    )
    expert: Mapping[str, object] | None = field(default_factory=lambda: {"tools": ["calculate"]})
    receipt: tuple[str, dict[str, object]] | None = None
    earlier_status: str | None = "succeeded"
    stored_goal: str | None = "The earlier goal"
    startup: dict[str, str] = field(default_factory=lambda: dict(STARTUP))


@dataclass(frozen=True)
class Reply:
    status_code: int
    body: dict[str, Any]


def post(client: ApiClient, arranged: Arranged, idempotency_key: str = "key-1") -> Reply:
    database = client.database
    database.answer("event_sequence = event_sequence + 1", (1,))
    database.answer("from app_private.model_invocations", (arranged.spent_today,))
    if arranged.daily_cap is not None:
        database.answer("from app_private.model_spend_limits", (arranged.daily_cap,))
    if arranged.saved_policy is not None:
        database.answer("from app_private.model_policies", arranged.saved_policy)
    if arranged.session is not None:
        database.answer("from public.sessions", arranged.session)
    if arranged.expert is not None:
        database.answer("from public.expert_versions", (arranged.expert,))
    if arranged.receipt is not None:
        database.answer("from app_private.idempotency_receipts", arranged.receipt)
    if arranged.earlier_status is not None:
        database.answer("select status from public.runs", (arranged.earlier_status,))
    if arranged.stored_goal is not None:
        database.answer("original_request", (arranged.stored_goal,))
    resources_of(client.app).provider_context = provider_context(environment=arranged.startup)
    client.app.dependency_overrides[require_ready] = lambda: None
    client.app.dependency_overrides[model_key_check] = lambda: (
        KeyCheck(arranged.key, client.log).run_intent
    )
    headers = client.headers(arranged.user, **{"Idempotency-Key": idempotency_key})
    response = client.http.post("/v1/runs", headers=headers, json=arranged.body)
    return Reply(response.status_code, response.json())


def refusal(reply: Reply) -> tuple[int, str, str]:
    assert set(reply.body) == {"code", "message"}
    return reply.status_code, reply.body["code"], reply.body["message"]


LABELS = {
    "app_private.model_spend_limits": "daily cap",
    "app_private.model_invocations": "spent today",
    "app_private.model_policies": "workspace policy",
    "public.sessions": "session",
    "public.expert_versions": "expert version",
    "app_private.provider_credentials": "saved keys",
    "app_private.tool_key_settings": "saved values",
    "app_private.tool_switches": "tool switches",
    "original_request": "stored goal",
}


def trace(client: ApiClient) -> list[str]:
    """What admission consulted, in order. `runs.admit`'s own statements, which
    tests/test_run_admission.py covers, are shown as its transaction's start and end."""
    steps: list[str] = []
    inside = False
    for entry in client.log:
        if entry == "begin":
            inside = True
            steps.append("admit")
        elif entry in {"commit", "rollback"}:
            inside = False
            steps.append("committed" if entry == "commit" else "rolled back")
        elif not inside:
            steps.append(next((name for part, name in LABELS.items() if part in entry), entry))
    return steps


def run_row(client: ApiClient) -> dict[str, Any]:
    """The admitted run's row, by the insert's column order in runs._insert_run_and_job."""
    (values,) = client.database.written("public.runs")
    assert isinstance(values, tuple)
    names = (
        "id workspace status limit goal summary snapshot continues session expert version "
        "parent root contract started_by parent_again yolo_parent yolo_workspace"
    ).split()
    return dict(zip(names, values, strict=True))


ADMITTED_TRACE = [
    "run_intent",
    "connect",
    "workspace policy",
    "session",
    "expert version",
    "saved keys",
    "saved values",
    "tool switches",
    "admit",
    "committed",
    "release",
]


# Admitted


def test_a_request_through_a_session_is_admitted_after_every_check(api_client: ApiClient) -> None:
    reply = post(api_client, Arranged())
    assert reply.status_code == 202
    body = reply.body
    assert body == {
        "schema_version": 1,
        "run_id": body["run_id"],
        "version": 1,
        "status": "queued",
        "replayed": False,
    }
    assert trace(api_client) == ADMITTED_TRACE
    row = run_row(api_client)
    assert (row["workspace"], row["limit"], row["started_by"]) == (WORKSPACE, 1_000_000, OWNER)
    assert (row["session"], row["expert"], row["version"]) == (SESSION, EXPERT, 1)
    assert json.loads(row["snapshot"])["bindings"]["executor"] == "openrouter_terra"
    assert UUID(body["run_id"]) == row["id"]


def test_a_plain_goal_reads_no_session_and_no_tool_keys(api_client: ApiClient) -> None:
    reply = post(api_client, Arranged(body=dict(GOAL)))
    assert reply.status_code == 202
    assert trace(api_client) == [
        "run_intent",
        "connect",
        "workspace policy",
        "admit",
        "committed",
        "release",
    ]
    row = run_row(api_client)
    assert (row["session"], row["expert"], row["version"]) == (None, None, None)


def test_a_repeat_with_the_same_content_replays_the_first_answer(api_client: ApiClient) -> None:
    first = post(api_client, Arranged())
    assert first.status_code == 202
    (receipt,) = api_client.database.written("app_private.idempotency_receipts")
    assert isinstance(receipt, tuple)
    written = len(api_client.database.changes())
    stored = {"run_id": str(REPLAYED), "version": 3, "status": "running"}
    again = post(api_client, Arranged(receipt=(receipt[5], stored)))
    assert again.status_code == 202
    assert again.body == {
        "schema_version": 1,
        "run_id": str(REPLAYED),
        "version": 3,
        "status": "running",
        "replayed": True,
    }
    assert len(api_client.database.changes()) == written


# (1) An Expert is chosen through a session


@pytest.mark.parametrize(
    "named",
    [
        {"expert_id": str(EXPERT)},
        {"expert_version": 2},
        {"expert_id": str(EXPERT), "expert_version": 2},
    ],
    ids=["an Expert", "a version", "both"],
)
def test_an_expert_without_a_session_is_refused_before_anything_is_read(
    api_client: ApiClient, named: dict[str, object]
) -> None:
    reply = post(api_client, Arranged(body={**GOAL, **named}))
    assert refusal(reply) == (422, "session_required", "An Expert is chosen through a session.")
    assert trace(api_client) == []


# (2) A budget or a limit


def test_a_budget_with_a_limit_is_refused_even_at_the_limits_default(
    api_client: ApiClient,
) -> None:
    body = {**GOAL, "budget_micro_usd": 500_000, "limit_micro_usd": 1_000_000}
    reply = post(api_client, Arranged(body=body))
    assert refusal(reply) == (422, "budget_conflict", "Choose a budget or a limit, not both.")
    assert trace(api_client) == []


@pytest.mark.parametrize(
    ("budget", "daily_cap", "spent", "expected"),
    [
        (
            100_000,
            None,
            0,
            (422, "budget_out_of_range", "Choose a budget from US$0.25 to US$5.00."),
        ),
        (
            5_250_000,
            None,
            0,
            (422, "budget_out_of_range", "Choose a budget from US$0.25 to US$5.00."),
        ),
        (300_000, None, 0, (422, "budget_off_step", "Choose a budget in steps of US$0.25.")),
        (
            750_000,
            1_000_000,
            500_000,
            (
                409,
                "budget_above_daily_cap",
                "That budget is more than what's left of today's spending cap.",
            ),
        ),
    ],
    ids=["below the range", "above the range", "off step", "above what's left today"],
)
def test_a_budget_outside_the_rules_is_refused_on_a_connection_of_its_own(
    api_client: ApiClient,
    budget: int,
    daily_cap: int | None,
    spent: int,
    expected: tuple[int, str, str],
) -> None:
    arranged = Arranged(body={**GOAL, "budget_micro_usd": budget}, daily_cap=daily_cap)
    reply = post(api_client, replace(arranged, spent_today=spent))
    assert refusal(reply) == expected
    assert trace(api_client) == ["connect", "daily cap", "spent today", "release"]


def test_a_budget_within_the_rules_becomes_the_frozen_limit(api_client: ApiClient) -> None:
    arranged = Arranged(body={**GOAL, "budget_micro_usd": 750_000}, daily_cap=1_000_000)
    reply = post(api_client, replace(arranged, spent_today=250_000))
    assert reply.status_code == 202
    assert trace(api_client)[:6] == [
        "connect",
        "daily cap",
        "spent today",
        "release",
        "run_intent",
        "connect",
    ]
    assert run_row(api_client)["limit"] == 750_000


def test_with_no_budget_the_requests_limit_is_frozen_and_no_spend_is_read(
    api_client: ApiClient,
) -> None:
    reply = post(api_client, Arranged(body={**GOAL, "limit_micro_usd": 40_000}))
    assert reply.status_code == 202
    assert "spent today" not in trace(api_client)
    assert run_row(api_client)["limit"] == 40_000


# (3) A usable OpenRouter key


@pytest.mark.parametrize(
    "code", ["credentials_required", "credential_invalid", "credential_unavailable"]
)
def test_without_a_usable_key_nothing_else_is_read(api_client: ApiClient, code: str) -> None:
    reply = post(api_client, Arranged(key=code, body={**THROUGH_SESSION, "expert_version": 1}))
    assert refusal(reply) == (409, code, KEY_NEEDED)
    assert trace(api_client) == ["run_intent"]


# (4) and (5) Only an owner pins an Expert version, then the saved policy is read


def test_a_member_choosing_an_expert_version_is_refused(api_client: ApiClient) -> None:
    arranged = Arranged(user=MEMBER, body={**THROUGH_SESSION, "expert_version": 1})
    reply = post(api_client, arranged)
    assert refusal(reply) == (403, "owner_required", "Only an owner can choose an Expert version.")
    assert trace(api_client) == ["run_intent", "role_in"]


def test_an_owner_may_choose_an_expert_version(api_client: ApiClient) -> None:
    arranged = Arranged(body={**THROUGH_SESSION, "expert_version": 2})
    reply = post(api_client, replace(arranged, session=("direct", [{"expert_id": str(EXPERT)}])))
    assert reply.status_code == 202
    assert trace(api_client)[:5] == [
        "run_intent",
        "role_in",
        "connect",
        "workspace policy",
        "session",
    ]
    assert run_row(api_client)["version"] == 2


def test_a_member_running_in_a_session_is_never_asked_for_a_role(api_client: ApiClient) -> None:
    reply = post(api_client, Arranged(user=MEMBER))
    assert reply.status_code == 202
    assert "role_in" not in trace(api_client)
    assert run_row(api_client)["started_by"] == MEMBER


# (6) The session's routing resolves


@pytest.mark.parametrize(
    ("arranged", "expected"),
    [
        (Arranged(session=None), (404, "session_not_found", ROUTING)),
        (
            Arranged(body={**GOAL, "session_id": str(SESSION)}, session=("coordinator", [])),
            (409, "route_needs_expert", ROUTING),
        ),
        (
            Arranged(body={**THROUGH_SESSION, "expert_id": str(ANOTHER_EXPERT)}),
            (409, "route_not_granted", ROUTING),
        ),
        (Arranged(expert=None), (404, "expert_version_not_found", ROUTING)),
    ],
    ids=["no such session", "coordinator without an Expert", "Expert not granted", "no version"],
)
def test_routing_that_doesnt_resolve_is_refused(
    api_client: ApiClient, arranged: Arranged, expected: tuple[int, str, str]
) -> None:
    assert refusal(post(api_client, arranged)) == expected
    assert trace(api_client)[-1] == "release"
    assert "admit" not in trace(api_client)
    assert api_client.database.changes() == []


# (7) No granted tool is unavailable (PK-02)


def test_a_granted_tool_without_its_key_in_the_startup_environment_is_refused(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The live environment's key doesn't count: availability reads what the entry point read at
    start (Decisions 0024 K1 and 0025 V3)."""
    monkeypatch.setenv("TAVILY_API_KEY", "tvly-live-only")
    reply = post(api_client, Arranged(expert={"tools": ["tavily_search"]}))
    assert refusal(reply) == (409, "tool_unavailable", TOOL_MISSING)
    assert trace(api_client) == [*ADMITTED_TRACE[:8], "release"]


def test_a_granted_tool_with_its_key_read_at_start_is_admitted(
    api_client: ApiClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    arranged = Arranged(expert={"tools": ["tavily_search"]})
    reply = post(api_client, replace(arranged, startup={"TAVILY_API_KEY": "tvly-read-at-start"}))
    assert reply.status_code == 202


# (8) Every resolved profile is offered


@pytest.mark.parametrize(
    ("arranged", "status"),
    [
        (Arranged(body={**GOAL, "run_profile": "openrouter_deepseek_flash"}), 422),
        (Arranged(body=dict(GOAL), saved_policy=("openrouter_deepseek_flash", {})), 409),
        (
            Arranged(
                body=dict(GOAL), saved_policy=(None, {"executor": "openrouter_deepseek_flash"})
            ),
            409,
        ),
        (
            Arranged(
                body={**THROUGH_SESSION, "run_profile": "openrouter_terra"},
                expert={"tools": [], "role_bindings": {"executor": "openrouter_deepseek_flash"}},
            ),
            409,
        ),
    ],
    ids=[
        "named in this request",
        "the saved default",
        "a saved role override",
        "an Expert's binding, with an offered profile named",
    ],
)
def test_a_profile_not_offered_is_refused_as_a_bad_request_only_when_named_here(
    api_client: ApiClient, arranged: Arranged, status: int
) -> None:
    assert refusal(post(api_client, arranged)) == (status, "model_not_offered", DEEPSEEK)
    assert trace(api_client)[-1] == "release"
    assert api_client.database.changes() == []


def test_an_offered_profile_named_here_is_frozen_for_every_role(api_client: ApiClient) -> None:
    reply = post(api_client, Arranged(body={**GOAL, "run_profile": "openrouter_sol"}))
    assert reply.status_code == 202
    bindings = json.loads(run_row(api_client)["snapshot"])["bindings"]
    assert set(bindings.values()) == {"openrouter_sol"}


# (9) The run is admitted under its key


def test_a_key_used_with_other_content_is_refused(api_client: ApiClient) -> None:
    stored = {"run_id": str(REPLAYED), "version": 1, "status": "queued"}
    reply = post(api_client, Arranged(receipt=("0" * 64, stored)))
    assert refusal(reply) == (
        409,
        "idempotency_conflict",
        "This key was already used with different content.",
    )
    assert trace(api_client) == [*ADMITTED_TRACE[:8], "admit", "rolled back", "release"]
    assert api_client.database.changes() == []


CONTINUE_REFUSED = (
    409,
    "run_not_continuable",
    "Only a finished goal run of its own, in this workspace, can be continued.",
)


def test_only_an_ended_run_can_be_continued(api_client: ApiClient) -> None:
    body = {**GOAL, "continues_run_id": str(EARLIER)}
    reply = post(api_client, Arranged(body=body, earlier_status="running"))
    assert refusal(reply) == CONTINUE_REFUSED
    assert trace(api_client)[-3:] == ["admit", "rolled back", "release"]
    assert api_client.database.changes() == []


def test_repeating_a_goal_needs_one_stored_before_anything_is_locked(api_client: ApiClient) -> None:
    body: dict[str, object] = {"continues_run_id": str(EARLIER)}
    reply = post(api_client, Arranged(body=body, stored_goal=None))
    assert refusal(reply) == CONTINUE_REFUSED
    assert trace(api_client)[-2:] == ["stored goal", "release"]


# Before any of them: the installation gate (LM-07)


def test_an_install_that_isnt_ready_refuses_before_any_step(api_client: ApiClient) -> None:
    def not_ready() -> None:
        raise ApiError(503, "not_ready", "Local services aren't ready, so nothing was started.")

    arranged = Arranged()
    post(api_client, arranged)
    api_client.log.clear()
    api_client.app.dependency_overrides[require_ready] = not_ready
    headers = api_client.headers(OWNER, **{"Idempotency-Key": "key-2"})
    response = api_client.http.post("/v1/runs", headers=headers, json=arranged.body)
    assert refusal(Reply(response.status_code, response.json()))[:2] == (503, "not_ready")
    assert api_client.log == []


# Which refusal wins


def no_session(arranged: Arranged) -> None:
    arranged.body.pop("session_id", None)


def budget_off_step(arranged: Arranged) -> None:
    arranged.body["budget_micro_usd"] = 300_000


def key_missing(arranged: Arranged) -> None:
    arranged.key = "credentials_required"


def member_pins_a_version(arranged: Arranged) -> None:
    arranged.user = MEMBER
    arranged.body["expert_version"] = 1


def session_gone(arranged: Arranged) -> None:
    arranged.session = None


def tool_without_its_key(arranged: Arranged) -> None:
    arranged.expert = {"tools": ["tavily_search"]}


def deepseek_named(arranged: Arranged) -> None:
    arranged.body["run_profile"] = "openrouter_deepseek_flash"


def key_reused(arranged: Arranged) -> None:
    arranged.receipt = ("0" * 64, {"run_id": str(REPLAYED), "version": 1, "status": "queued"})


# Each refusing step in admission order: what makes it refuse, and its answer.
STEPS: list[tuple[str, Callable[[Arranged], None], tuple[int, str, str]]] = [
    ("1 session", no_session, (422, "session_required", "An Expert is chosen through a session.")),
    ("2 budget", budget_off_step, (422, "budget_off_step", "Choose a budget in steps of US$0.25.")),
    ("3 key", key_missing, (409, "credentials_required", KEY_NEEDED)),
    (
        "4 version pin",
        member_pins_a_version,
        (403, "owner_required", "Only an owner can choose an Expert version."),
    ),
    ("6 routing", session_gone, (404, "session_not_found", ROUTING)),
    ("7 tools", tool_without_its_key, (409, "tool_unavailable", TOOL_MISSING)),
    ("8 offered", deepseek_named, (422, "model_not_offered", DEEPSEEK)),
    (
        "9 admission",
        key_reused,
        (409, "idempotency_conflict", "This key was already used with different content."),
    ),
]


@pytest.mark.parametrize(
    ("earlier", "later"),
    list(combinations(range(len(STEPS)), 2)),
    ids=[f"{STEPS[a][0]} before {STEPS[b][0]}" for a, b in combinations(range(len(STEPS)), 2)],
)
def test_the_earlier_step_refuses_when_two_would(
    api_client: ApiClient, earlier: int, later: int
) -> None:
    arranged = Arranged()
    STEPS[later][1](arranged)
    STEPS[earlier][1](arranged)
    assert refusal(post(api_client, arranged)) == STEPS[earlier][2]
    assert api_client.database.changes() == []


@pytest.mark.parametrize("step", range(len(STEPS)), ids=[name for name, _, _ in STEPS])
def test_each_step_alone_refuses_with_its_own_answer(api_client: ApiClient, step: int) -> None:
    arranged = Arranged()
    STEPS[step][1](arranged)
    assert refusal(post(api_client, arranged)) == STEPS[step][2]
    assert api_client.database.changes() == []
