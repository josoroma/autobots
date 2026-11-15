"""The commands a run's page offers a person, as `RunWorkspace.allowed_commands` (R-49, WRUN-12).

The service computes them with SP-010's `next_status` for a person, so the page never re-derives
the command table. The pause, resume and cancel routes admit any member of the workspace, so an
owner and a member are offered the same commands.
"""

from collections.abc import Iterator
from typing import get_args

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from autobots.api import run_command_routes, run_reconcile_routes
from autobots.api.dependencies import current_workspace, require_owner
from autobots.application.run_projection import user_commands
from autobots.contracts.run_workspace import RunWorkspace, UserRunCommand
from autobots.domain.runs import Actor, CommandRefused, RunCommand, RunStatus, next_status

# SP-010's commands a person may send from each status, in the page's order.
OFFERED: dict[RunStatus, list[str]] = {
    RunStatus.QUEUED: ["pause", "cancel"],
    RunStatus.RUNNING: ["pause", "cancel"],
    RunStatus.WAITING_INPUT: ["pause", "cancel"],
    RunStatus.WAITING_APPROVAL: ["pause", "cancel"],
    RunStatus.PAUSED: ["resume", "cancel"],
    RunStatus.VERIFYING: ["pause", "cancel"],
    RunStatus.CANCELLING: [],
    RunStatus.SUCCEEDED: [],
    RunStatus.FAILED: [],
    RunStatus.CANCELLED: [],
}


def test_each_status_offers_what_sp010_lets_a_person_do() -> None:
    assert {status: user_commands(status) for status in RunStatus} == OFFERED


def test_a_command_is_offered_exactly_when_next_status_moves_the_run() -> None:
    # A refusal and a repeated cancellation, which changes nothing, are both left out.
    for status in RunStatus:
        for name in get_args(UserRunCommand):
            try:
                moves = next_status(status, RunCommand(name), Actor.USER) is not None
            except CommandRefused:
                moves = False
            assert (name in user_commands(status)) is moves, (status, name)


def test_the_offered_names_are_commands_a_worker_cannot_send() -> None:
    for name in get_args(UserRunCommand):
        with pytest.raises(CommandRefused):
            next_status(RunStatus.PAUSED, RunCommand(name), Actor.WORKER)
    assert RunWorkspace.model_fields["allowed_commands"].annotation == list[UserRunCommand]


def _calls(dependant: Dependant) -> Iterator[object]:
    for dependency in dependant.dependencies:
        if dependency.call is not None:
            yield dependency.call
        yield from _calls(dependency)


def _depends_on(path: str) -> set[object]:
    for route in [*run_command_routes.router.routes, *run_reconcile_routes.router.routes]:
        if isinstance(route, APIRoute) and route.path == path and route.methods == {"POST"}:
            return set(_calls(route.dependant))
    raise AssertionError(f"no POST route at {path}")


@pytest.mark.parametrize("command", ["pause", "resume", "cancel"])
def test_any_member_may_send_a_command_so_owner_and_member_are_offered_the_same(
    command: str,
) -> None:
    # An owner-only rule here would make the field differ by role, so it would have to take one.
    needs = _depends_on(f"/v1/runs/{{run_id}}/{command}")
    assert current_workspace in needs
    assert require_owner not in needs


def test_the_dependency_walk_finds_an_owner_only_route() -> None:
    assert require_owner in _depends_on("/v1/runs/{run_id}/model-calls/reconcile")
