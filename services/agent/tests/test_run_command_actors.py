"""Who may apply each run command, as SP-010's command table in the Option B contract states it
(Decision 0029 F5, PRUN-07).

The domain's table and the contract's are compared row by row, so neither can grant an actor a
command the other doesn't. The system applies only cancel, pause and resume.
"""

import re
from pathlib import Path

import pytest

from autobots.domain.runs import ACTORS, Actor, CommandRefused, RunCommand, RunStatus, next_status

CONTRACT = Path(__file__).resolve().parents[3] / "docs/engineering/option-b-contract.md"
HEADING = "#### Run commands and their actors"
Row = tuple[frozenset[str], frozenset[str], frozenset[str]]


def _names(cell: str) -> frozenset[str]:
    return frozenset(re.findall(r"`([a-z_]+)`", cell))


def contract_table() -> dict[str, Row]:
    """The table under HEADING: each command's actors, the states it moves from, and its targets."""
    section = CONTRACT.read_text().split(HEADING, 1)[1]
    rows: dict[str, Row] = {}
    for line in section.splitlines():
        if line.startswith("#"):
            break
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].startswith("`"):
            [command] = _names(cells[0])
            rows[command] = (_names(cells[1]), _names(cells[2]), _names(cells[3]))
    return rows


def domain_table() -> dict[str, Row]:
    """The same three columns, read from `next_status` for each command and an actor it allows."""
    rows: dict[str, Row] = {}
    for command in RunCommand:
        actor = next(iter(ACTORS[command]))
        sources: set[str] = set()
        targets: set[str] = set()
        for current in RunStatus:
            for active in (False, True):
                try:
                    reached = next_status(current, command, actor, has_active_work=active)
                except CommandRefused:
                    continue
                if reached is not None:
                    sources.add(current.value)
                    targets.add(reached.value)
        actors = frozenset(item.value for item in ACTORS[command])
        rows[command.value] = (actors, frozenset(sources), frozenset(targets))
    return rows


def test_the_contract_lists_each_command_as_the_domain_applies_it() -> None:
    assert contract_table() == domain_table()


def test_every_command_names_its_actors() -> None:
    assert set(ACTORS) == set(RunCommand)
    assert all(ACTORS[command] for command in RunCommand)


def test_the_system_applies_only_cancel_pause_and_resume() -> None:
    """A parent's cancel and resume reaching its children, a stray child's cancel, and an
    approval's expiry pausing its run (Decision 0029 F5)."""
    allowed = {command for command in RunCommand if Actor.SYSTEM in ACTORS[command]}
    assert allowed == {RunCommand.CANCEL, RunCommand.PAUSE, RunCommand.RESUME}


@pytest.mark.parametrize("command", [RunCommand.CANCEL, RunCommand.RESUME, RunCommand.PAUSE])
def test_a_worker_never_cancels_resumes_or_pauses(command: RunCommand) -> None:
    for current in RunStatus:
        with pytest.raises(CommandRefused):
            next_status(current, command, Actor.WORKER)


@pytest.mark.parametrize(
    "command", [command for command in RunCommand if Actor.WORKER in ACTORS[command]]
)
def test_neither_a_person_nor_the_system_applies_a_workers_command(command: RunCommand) -> None:
    for actor in (Actor.USER, Actor.SYSTEM):
        with pytest.raises(CommandRefused):
            next_status(RunStatus.RUNNING, command, actor)


def test_a_claim_moves_only_a_queued_run() -> None:
    """Without its source a claim of a verifying run would reach running, as a repair does."""
    assert next_status(RunStatus.QUEUED, RunCommand.CLAIM, Actor.WORKER) is RunStatus.RUNNING
    for current in set(RunStatus) - {RunStatus.QUEUED}:
        with pytest.raises(CommandRefused):
            next_status(current, RunCommand.CLAIM, Actor.WORKER)
