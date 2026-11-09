"""US-14.19 offline: `cronjob` v1's input rules, approval per action and catalog entry."""

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from autobots.application.cronjob_tool import CRONJOB, routine_config
from autobots.application.tool_catalog import all_descriptors, latest
from autobots.contracts.cronjob import CronjobInput, CronjobTask

TASK = {
    "target_kind": "expert",
    "target_id": str(uuid4()),
    "target_version": 1,
    "schedule": {"kind": "daily", "time": "08:30"},
    "goal": "Summarize",
}
ROUTINE = str(uuid4())


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
    assert CRONJOB.approval_when is not None
    assert CRONJOB.approval_when(parsed) is (arguments["action"] != "list")


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


def test_a_schedule_becomes_the_routine_trigger() -> None:
    daily = routine_config(CronjobTask.model_validate(TASK))
    assert daily.trigger == {"kind": "daily", "time": "08:30"}
    interval = routine_config(
        CronjobTask.model_validate({**TASK, "schedule": {"kind": "interval", "minutes": 15}})
    )
    assert interval.trigger == {"kind": "interval", "minutes": 15}


def test_the_catalog_lists_it_under_automation_for_experts_only() -> None:
    item = next(d for d in latest(all_descriptors({})) if d.tool_id == "cronjob")
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
