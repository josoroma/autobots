"""US-14.19 offline: `cronjob` v1's input rules, approval per action and catalog entry."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.adapters.tool_registry import catalog
from autobots.application import cronjob_tool as cronjob_module
from autobots.application.cronjob_tool import cronjob_tool, routine_config
from autobots.application.routines import RoutineRefused, routine_record
from autobots.application.tool_catalog import latest
from autobots.application.tool_definitions import ToolContext, ToolFailed
from autobots.contracts.cronjob import (
    MAX_LIMIT_MICRO_USD,
    CronjobInput,
    CronjobOutput,
    CronjobTask,
)
from fake_api import FakeConnection, FakeDatabase

TASK = {
    "target_kind": "expert",
    "target_id": str(uuid4()),
    "target_version": 1,
    "schedule": {"kind": "daily", "time": "08:30"},
    "goal": "Summarize",
}
ROUTINE = str(uuid4())
CATALOG = catalog()
CRONJOB = cronjob_tool(CATALOG)


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "list"},
        {"action": "create", "name": "Weekly", "task": TASK},
        {"action": "update", "routine_id": ROUTINE, "expected_version": 1, "task": TASK},
        {"action": "pause", "routine_id": ROUTINE},
        {"action": "resume", "routine_id": ROUTINE},
        {"action": "run", "routine_id": ROUTINE},
        {"action": "remove", "routine_id": ROUTINE},
    ],
)
def test_each_action_takes_its_own_fields(arguments: dict[str, Any]) -> None:
    parsed = CronjobInput.model_validate(arguments)
    assert CRONJOB.approval.when is not None
    assert CRONJOB.approval.when(parsed) is (arguments["action"] != "list")


@pytest.mark.parametrize(
    "arguments",
    [
        {"action": "list", "routine_id": ROUTINE},
        {"action": "create", "name": "Weekly"},
        {"action": "create", "task": TASK},
        {"action": "update", "routine_id": ROUTINE, "task": TASK},
        {"action": "pause"},
        {"action": "remove", "routine_id": ROUTINE, "name": "x"},
        {"action": "delete", "routine_id": ROUTINE},
        {"action": "create", "name": "W", "task": {**TASK, "schedule": {"kind": "daily"}}},
        {
            "action": "create",
            "name": "W",
            "task": {**TASK, "schedule": {"kind": "interval", "minutes": 0}},
        },
        {
            "action": "create",
            "name": "W",
            "task": {**TASK, "schedule": {"kind": "daily", "time": "25:00"}},
        },
        {"action": "create", "name": "W", "task": {**TASK, "limit_micro_usd": 1_000_001}},
        {"action": "create", "name": "W", "task": {**TASK, "shell": "rm"}},
    ],
)
def test_anything_else_is_refused_before_the_gateway(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CronjobInput.model_validate(arguments)


def test_the_v1_schema_is_unchanged() -> None:
    """`cronjob` v1's input and output schemas, byte for byte as captured before R-52 moved its
    schedule into contracts/routines.py, where the Routines API shares it (Decision 0026 C1)."""
    captured = json.loads((Path(__file__).parent / "fixtures/cronjob_v1_schema.json").read_text())
    current = {
        "input": CronjobInput.model_json_schema(),
        "output": CronjobOutput.model_json_schema(),
    }
    assert json.dumps(current, indent=2) == json.dumps(captured, indent=2)


def test_a_schedule_becomes_the_routine_trigger_as_it_was_stored() -> None:
    daily = routine_config(CronjobTask.model_validate(TASK))
    assert daily.trigger.model_dump(exclude_none=True) == {"kind": "daily", "time": "08:30"}
    assert json.loads(routine_record(daily).stored())["trigger"] == {
        "kind": "daily",
        "time": "08:30",
    }
    interval = routine_config(
        CronjobTask.model_validate({**TASK, "schedule": {"kind": "interval", "minutes": 15}})
    )
    assert json.loads(routine_record(interval).stored())["trigger"] == {
        "kind": "interval",
        "minutes": 15,
    }


@pytest.mark.parametrize(
    ("arguments", "service"),
    [
        ({"action": "create", "name": "Weekly", "task": TASK}, "create_routine"),
        (
            {"action": "update", "routine_id": ROUTINE, "expected_version": 1, "task": TASK},
            "add_routine_version",
        ),
    ],
)
def test_a_routine_the_model_saves_carries_the_tools_cap(
    monkeypatch: pytest.MonkeyPatch, arguments: dict[str, Any], service: str
) -> None:
    """Decision 0029 F2: the cronjob tool states its US$1 cap to the routine service, which the
    Routines API, for a person's routine, does not."""
    called: dict[str, object] = {}

    async def saved(*_args: object, **kwargs: object) -> object:
        called.update(kwargs)
        raise RoutineRefused("routine_limit_too_high")

    monkeypatch.setattr(cronjob_module, service, saved)
    database = FakeDatabase([])
    database.answer("coalesce(r.started_by", (str(uuid4()),))
    # Only what the handler reads: the connection, the run's scope and the call's operation id.
    context = SimpleNamespace(
        connection=FakeConnection(database),
        scope=SimpleNamespace(workspace_id=uuid4(), run_id=uuid4()),
        operation_id="operation",
    )

    async def call() -> object:
        return await CRONJOB.handler(
            CronjobInput.model_validate(arguments), cast("ToolContext", context)
        )

    with pytest.raises(ToolFailed, match="routine_limit_too_high"):
        asyncio.run(call())
    assert called["budget_cap"] == MAX_LIMIT_MICRO_USD == 1_000_000


def test_the_catalog_lists_it_under_automation_for_experts_only() -> None:
    item = next(d for d in latest(CATALOG.descriptors({})) if d.tool_id == "cronjob")
    assert (item.group, item.approval, item.grantable_to, item.operation_class) == (
        "automation",
        "by_action",
        ["expert"],
        "reversible_internal_write",
    )
    public = {(field.direction, field.path) for field in item.fields if field.public}
    assert public == {
        ("input", "action"),
        ("input", "routine_id"),
        ("input", "name"),
        ("output", "routine_id"),
        ("output", "status"),
        ("output", "run_id"),
    }
