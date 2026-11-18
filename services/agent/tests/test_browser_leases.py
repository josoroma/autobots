"""What ends a browser session, offline: whether its attempt still owns a running run, and the
sweeper's check by the run and generation a container is labelled with (US-14.13, PRD-Tool-Catalog
BX-04, refactor plan R-57). Scripted rows stand in for the database; nothing starts Docker.
"""

from uuid import uuid4

import pytest

from autobots.adapters import browser_executor
from autobots.application import browser_leases
from autobots.application.browser_leases import GENERATION, OWNERSHIP, attempt_alive, lease_alive
from autobots.application.tool_definitions import ToolScope
from autobots.application.tool_gateway import ownership_refusal
from autobots.domain.stops import GatewayCode
from sql_fakes import ScriptedConnection

SCOPE = ToolScope(uuid4(), uuid4(), 3, {"browse_goal": 1})
COLUMNS = ("run_status", "job_status", "generation", "lease_live")
OWNED = ("running", "claimed", 3, True)


def ownership(*row: object) -> ScriptedConnection:
    return ScriptedConnection([dict(zip(COLUMNS, row, strict=True))] if row else [])


@pytest.mark.parametrize(
    ("row", "gateway"),
    [
        (OWNED, None),
        ((), GatewayCode.RUN_NOT_FOUND),
        (("running", "queued", 3, True), GatewayCode.LEASE_LOST),
        (("running", "claimed", 4, True), GatewayCode.LEASE_LOST),
        (("running", "claimed", 3, False), GatewayCode.LEASE_LOST),
        (("running", "claimed", 3, None), GatewayCode.LEASE_LOST),
        (("cancelling", "claimed", 3, True), GatewayCode.RUN_NOT_RUNNING),
        (("paused", "claimed", 3, True), GatewayCode.RUN_NOT_RUNNING),
    ],
)
@pytest.mark.asyncio
async def test_a_session_lives_exactly_while_the_gateway_would_admit_its_attempt(
    row: tuple[object, ...], gateway: GatewayCode | None
) -> None:
    """A cancel, a lost lease or a newer claim ends the session, as each ends the attempt."""
    assert await ownership_refusal(ownership(*row), SCOPE) is gateway
    assert await attempt_alive(ownership(*row), SCOPE) is (gateway is None)


@pytest.mark.asyncio
async def test_the_session_reads_the_statement_the_gateway_reads() -> None:
    """Held apart so the images' fingerprint binds it; a change to either fails here, and a change
    to this copy turns browsing off until it is qualified again."""
    session, gateway = ownership(*OWNED), ownership(*OWNED)
    await attempt_alive(session, SCOPE)
    await ownership_refusal(gateway, SCOPE)
    assert session.statements == gateway.statements == [OWNERSHIP]


@pytest.mark.asyncio
async def test_the_sweeper_keeps_a_session_only_while_its_generation_holds_the_run() -> None:
    held, lost = ScriptedConnection([(1,)]), ScriptedConnection()
    assert await lease_alive(held)("run-id", 3)
    assert not await lease_alive(lost)("run-id", 3)
    assert held.statements == lost.statements == [GENERATION]
    for fragment in ("j.status = 'claimed'", "clock_timestamp()", "r.status = 'running'"):
        assert fragment in GENERATION


def test_the_executor_module_still_offers_the_session_checks() -> None:
    """tests/db/checks/browser_executor_check.py imports them from there."""
    assert browser_executor.attempt_alive is browser_leases.attempt_alive
    assert browser_executor.lease_alive is browser_leases.lease_alive
