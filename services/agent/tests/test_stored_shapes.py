"""Every stored shape of a jsonb record still reads, and a write keeps today's shape (refactor plan
R-52, PDOM-01).

Each fixture under fixtures/stored/<record>/ is a document a release wrote, or an older contract's
shape that the history shows was written, and says what wrote it. A record must read each one and
map to the contract its readers use. Removing a field or tightening a bound that a stored document
holds then fails here, before a saved Expert, routine or goal stops reading.
"""

import asyncio
import json
from collections.abc import Awaitable
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from autobots.adapters.tool_registry import catalog
from autobots.application import routines as routines_module
from autobots.application.experts import expert_record, expert_view_config
from autobots.application.plans import goal_spec, plan_task, plan_task_record
from autobots.application.routines import (
    RoutineRefused,
    add_routine_version,
    create_routine,
    evaluate_routines,
    routine_record,
    routine_view_config,
)
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.plans import GoalSpec, PlanTask
from autobots.contracts.primitives import MAX_SAFE_INTEGER
from autobots.contracts.routines import RoutineConfig
from autobots.domain.routines import (
    MODEL_ROUTINE_LIMIT_MICRO_USD,
    DailyTrigger,
    IntervalTrigger,
    TriggerInvalid,
    UnscheduledTrigger,
    occurrences,
)
from autobots.persistence.records import (
    read_expert_config,
    read_goal_spec,
    read_plan_tasks,
    read_routine_config,
)
from fake_api import FakeConnection, FakeDatabase

STORED = Path(__file__).parent / "fixtures/stored"
WORKSPACE = UUID("0d000000-0000-4000-8000-0000000000a1")
ACTOR = UUID("0d000000-0000-4000-8000-0000000000a2")
ROUTINE = UUID("0d000000-0000-4000-8000-0000000000a3")


def documents(record: str) -> dict[str, Any]:
    return {
        path.stem: json.loads(path.read_text())["stored"]
        for path in sorted((STORED / record).glob("*.json"))
    }


EXPERTS = documents("expert_config")
ROUTINES = documents("routine_config")
GOALS = documents("goal_spec")
PLANS = documents("plan_tasks")
# What today's writers store, as captured from them before R-52 (fixtures say which wrote each).
WRITTEN_ROUTINES = (
    "api_daily",
    "api_interval_workflow",
    "api_limit_above_tool_cap",
    "cronjob_daily",
    "cronjob_interval_workflow",
)
# Each create and edit receipt's request_hash for those, captured from the same code: a retry
# across the upgrade still matches its receipt.
FINGERPRINTS = {
    "api_daily": (
        "b14499d834373218cadedce5ca5e3acfd5939ae45c858d58cd8bdcaeaa587d9f",
        "0116c53bbb5d13914dc2661daf0104850d951e59e569bc5954df6b8923eec4d5",
    ),
    "api_interval_workflow": (
        "e02a41010eac6722efe97c4ff0871e52761e4ee5b265ab17ae374de2791ca0f7",
        "48e54ed646d76cc223627773fc0880ba582f89805cc3cd510438dea3a6bee5c9",
    ),
    "api_limit_above_tool_cap": (
        "22b13428c4322c724652a601d2dae0a338beee2142591df0c9ba817a58f3c41d",
        "2f7794e68b8472f25df2dab0f9be26b2f013c1f42ea409feb404d213c7959c4a",
    ),
    "cronjob_daily": (
        "e8cb5e6b0113f310fbf3e48d7e2c764630c765639af08b276425af1b05324c3e",
        "9392efadffa7befce1f58eab23822edfe38c28c04d174370b4c45e39250c326b",
    ),
    "cronjob_interval_workflow": (
        "432c4522faeb46682faabd0870c105dcd6478a2bfca0a8de654cae0b588bd93c",
        "33ae28d1c957944a68aad0a8043e3fd777515cd316aa6e52c9ba571f6945c876",
    ),
}
# The wall-clock time each daily routine runs at, which its view shows, so a view never misstates
# when a routine runs: an offset never moved one, and seconds do.
RUNS_AT = {
    "api_daily": "09:00",
    "api_daily_compact": "07:30",
    "api_daily_hour_only": "07:00",
    "api_daily_utc_suffix": "07:30",
    "api_daily_with_fraction": "07:30:45.500000",
    "api_daily_with_offset": "07:30",
    "api_daily_with_seconds": "07:30:45",
    "api_daily_with_t": "07:30",
    "api_daily_zero_seconds": "07:30",
    "cronjob_daily": "08:30",
}


def run[T](step: Awaitable[T]) -> T:
    async def awaited() -> T:
        return await step

    return asyncio.run(awaited())


# Expert configurations


# What a version's view holds for a field its stored document leaves out.
EXPERT_DEFAULTS = {
    "purpose": "",
    "instructions": "",
    "tools": [],
    "tool_groups": [],
    "skills": [],
    "role_bindings": {},
}


@pytest.mark.parametrize("name", sorted(EXPERTS))
def test_every_stored_expert_config_reads_and_shows_what_it_stores(name: str) -> None:
    view = expert_view_config(read_expert_config(EXPERTS[name]))
    assert view.model_dump(mode="json") == {**EXPERT_DEFAULTS, **EXPERTS[name]}


def test_an_expert_saved_past_a_request_bound_still_reads() -> None:
    """expand_groups can store more tools than a request may name, so the view has no bound."""
    stored = EXPERTS["groups_expanded_past_twenty_tools"]
    assert len(stored["tools"]) > 20
    with pytest.raises(ValidationError):
        ExpertConfig.model_validate(stored)
    assert expert_view_config(read_expert_config(stored)).tools == stored["tools"]


@pytest.mark.parametrize("name", ["current", "concept_seed"])
def test_saving_an_expert_config_stores_todays_shape(name: str) -> None:
    config = ExpertConfig.model_validate(EXPERTS[name])
    assert json.loads(expert_record(config).stored()) == EXPERTS[name]


def test_a_stored_record_ignores_a_field_it_does_not_know() -> None:
    record = read_expert_config({**EXPERTS["current"], "written_later": {"any": "value"}})
    assert record == read_expert_config(EXPERTS["current"])


def test_a_document_without_a_version_is_version_one_and_another_version_is_refused() -> None:
    assert read_expert_config(EXPERTS["current"]).record_version == 1
    assert read_expert_config({**EXPERTS["current"], "record_version": 1}).record_version == 1
    with pytest.raises(ValidationError):
        read_expert_config({**EXPERTS["current"], "record_version": 2})


# Routine configurations


@pytest.mark.parametrize("name", sorted(ROUTINES))
def test_every_stored_routine_config_reads_and_shows(name: str) -> None:
    record = read_routine_config(ROUTINES[name])
    view = routine_view_config(record)
    stored = ROUTINES[name]
    assert (view.target.kind, str(view.target.id), view.target.version) == (
        stored["target"]["kind"],
        stored["target"]["id"],
        stored["target"]["version"],
    )
    assert (view.timezone, view.goal, view.inputs, view.tools, view.trigger.kind) == (
        stored["timezone"],
        stored["goal"],
        stored["inputs"],
        stored["tools"],
        stored["trigger"]["kind"],
    )
    if view.trigger.kind == "daily":
        assert view.trigger.time == RUNS_AT.get(name)
    else:
        assert view.trigger.minutes == stored["trigger"]["minutes"]


@pytest.mark.parametrize("name", sorted(RUNS_AT))
def test_a_shown_daily_time_is_the_time_it_runs(name: str) -> None:
    record = read_routine_config(ROUTINES[name])
    shown = routine_view_config(record).trigger.time
    after = datetime(2026, 11, 5, tzinfo=UTC)
    first = occurrences(record.trigger, record.timezone, after, after + timedelta(days=2))[0]
    assert shown is not None
    assert first.astimezone(ZoneInfo(record.timezone)).time() == time.fromisoformat(shown)


def test_an_offset_in_an_older_daily_time_never_moved_it() -> None:
    """What the code before R-52 did with 07:30+05:00 in Costa Rica, observed: 13:30 UTC, the
    instant of 07:30 there, since the routine's own timezone replaces the offset."""
    offset = read_routine_config(ROUTINES["api_daily_with_offset"])
    plain = read_routine_config(
        {**ROUTINES["api_daily"], "trigger": {"kind": "daily", "time": "07:30"}}
    )
    after = datetime(2026, 11, 5, tzinfo=UTC)
    found = occurrences(offset.trigger, offset.timezone, after, after + timedelta(days=1))
    assert found == [datetime(2026, 11, 5, 13, 30, tzinfo=UTC)]
    assert found == occurrences(plain.trigger, plain.timezone, after, after + timedelta(days=1))


def test_older_triggers_parse_to_the_schedule_they_always_had() -> None:
    assert read_routine_config(ROUTINES["api_interval_extra_keys"]).trigger == IntervalTrigger(60)
    offset = read_routine_config(ROUTINES["api_daily_with_offset"])
    seconds = read_routine_config(ROUTINES["api_daily_with_seconds"])
    assert (offset.trigger, seconds.trigger) == (
        DailyTrigger(time(7, 30)),
        DailyTrigger(time(7, 30, 45)),
    )


def test_a_stored_daily_time_that_is_not_text_reads_and_never_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Before R-52 occurrences() raised on such a time, so the routine never ran. It still never
    runs: its evaluation fails with daily_time_invalid, admits nothing and leaves it due, which
    fails closed on money. Its view shows no time."""
    stored = ROUTINES["api_daily_time_not_text"]
    record = read_routine_config(stored)
    assert record.trigger == UnscheduledTrigger(1230)
    assert routine_view_config(record).trigger.time is None
    after = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(TriggerInvalid, match="daily_time_invalid"):
        occurrences(record.trigger, record.timezone, after, after + timedelta(days=400))
    database = FakeDatabase([])
    database.answer("select id from public.routines where enabled", (ROUTINE,))
    database.answer(
        "select workspace_id, latest_version, evaluated_until",
        {"workspace_id": WORKSPACE, "latest_version": 1, "evaluated_until": after},
    )
    database.answer("select clock_timestamp()", (datetime(2026, 11, 15, tzinfo=UTC),))
    database.answer("select config from public.routine_versions", (stored,))

    failed: list[object] = []
    monkeypatch.setattr(
        routines_module, "log_event", lambda *_args, **fields: failed.append(fields["error"])
    )

    async def ready(_workspace_id: UUID) -> str:
        return "ready"

    assert run(evaluate_routines(FakeConnection(database), ready, catalog=catalog())) == 0
    assert database.changes() == []
    (error,) = failed
    assert isinstance(error, TriggerInvalid) and error.code == "daily_time_invalid"


def test_a_limit_beyond_a_safe_integer_runs_as_stored_and_shows_capped() -> None:
    """Admission uses the stored value, which the workspace's run limit caps (Decision 0029 F2). A
    JavaScript client can't hold more than MAX_SAFE_INTEGER, so the view shows that."""
    record = read_routine_config(ROUTINES["api_limit_beyond_safe_integer"])
    assert record.limit_micro_usd == 2**60
    assert routine_view_config(record).limit_micro_usd == MAX_SAFE_INTEGER


@pytest.mark.parametrize("name", WRITTEN_ROUTINES)
def test_saving_a_routine_config_stores_todays_shape(name: str) -> None:
    config = RoutineConfig.model_validate(ROUTINES[name])
    assert json.loads(routine_record(config).stored()) == ROUTINES[name]


def routine_database(stored: object) -> FakeDatabase:
    """Its target exists, and the routine reads back as `stored`."""
    database = FakeDatabase([])
    expert = {"tools": ["calculate"]}
    database.answer("from public.experts e join public.expert_versions v", (expert,))
    database.answer("from public.workflow_versions v join public.workflows w", (1,))
    database.answer(
        "from public.routines where id",
        {"id": ROUTINE, "name": "Fixture", "enabled": True, "latest_version": 1},
    )
    database.answer('select latest_version from "public"."routines"', (1,))
    database.answer(
        "select v.routine_id, v.config from public.routine_versions",
        {"routine_id": ROUTINE, "config": stored},
    )
    return database


@pytest.mark.parametrize("name", WRITTEN_ROUTINES)
def test_the_routine_service_stores_and_fingerprints_as_it_did(name: str) -> None:
    config = RoutineConfig.model_validate(ROUTINES[name])
    created = routine_database(ROUTINES[name])
    run(
        create_routine(
            FakeConnection(created),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="fixture",
            name="Fixture",
            config=config,
            budget_cap=None,
        )
    )
    edited = routine_database(ROUTINES[name])
    view = run(
        add_routine_version(
            FakeConnection(edited),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            routine_id=ROUTINE,
            idempotency_key="fixture",
            expected_version=1,
            config=config,
            budget_cap=None,
        )
    )
    (first,) = created.written("public.routine_versions")
    (second,) = edited.written("public.routine_versions")
    (create_receipt,) = created.written("app_private.idempotency_receipts")
    (edit_receipt,) = edited.written("app_private.idempotency_receipts")
    assert isinstance(first, tuple) and isinstance(second, tuple)
    assert json.loads(first[1]) == json.loads(second[2]) == ROUTINES[name]
    assert isinstance(create_receipt, tuple) and isinstance(edit_receipt, tuple)
    assert (create_receipt[5], edit_receipt[5]) == FINGERPRINTS[name]
    assert view.config == routine_view_config(read_routine_config(ROUTINES[name]))


def test_a_persons_routine_keeps_the_run_limit_and_a_capped_one_is_refused_above_it() -> None:
    """Decision 0029 F2: the Routines API passes no cap, so a person's routine may take more than
    US$1 a run and the workspace's run limit caps it at admission. The cronjob tool passes the US$1
    cap, and the service refuses more."""
    config = RoutineConfig.model_validate(ROUTINES["api_limit_above_tool_cap"])
    saved = run(
        create_routine(
            FakeConnection(routine_database(ROUTINES["api_limit_above_tool_cap"])),
            workspace_id=WORKSPACE,
            actor_id=ACTOR,
            idempotency_key="person",
            name="Fixture",
            config=config,
            budget_cap=None,
        )
    )
    assert saved.config.limit_micro_usd == 5_000_000
    capped = routine_database(ROUTINES["api_limit_above_tool_cap"])
    with pytest.raises(RoutineRefused, match="routine_limit_too_high"):
        run(
            create_routine(
                FakeConnection(capped),
                workspace_id=WORKSPACE,
                actor_id=ACTOR,
                idempotency_key="model",
                name="Fixture",
                config=config,
                budget_cap=MODEL_ROUTINE_LIMIT_MICRO_USD,
            )
        )
    assert capped.changes() == []


# Goals and plans


@pytest.mark.parametrize("name", sorted(GOALS))
def test_every_stored_goal_reads_as_it_did(name: str) -> None:
    assert goal_spec(read_goal_spec(GOALS[name])) == GoalSpec.model_validate(GOALS[name])


@pytest.mark.parametrize("name", sorted(PLANS))
def test_every_stored_plan_reads_as_it_did(name: str) -> None:
    tasks = [plan_task(record) for record in read_plan_tasks(PLANS[name])]
    assert tasks == [PlanTask.model_validate(task) for task in PLANS[name]]


@pytest.mark.parametrize("name", sorted(PLANS))
def test_committing_a_plan_stores_todays_shape(name: str) -> None:
    tasks = [PlanTask.model_validate(task) for task in PLANS[name]]
    assert [plan_task_record(task).document() for task in tasks] == PLANS[name]
