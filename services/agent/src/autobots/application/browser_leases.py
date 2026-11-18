"""Whether a browser session's attempt still holds its run: the checks that end a session on a
cancel, a lost lease or a crashed worker, US-14.13, PRD-Tool-Catalog BX-04 and Decision 0018.

Both queries are held here, in the images' fingerprint (adapters/browser_qualification.py
FINGERPRINTED), so a change to what ends a session turns browsing off until it is qualified again
(refactor plan R-57, SQLI-02). They are application SQL on the run and lease tables, so they stay
out of the adapters (PADP-13), which call them through adapters/browser_executor.py.
`attempt_alive` reads the statement the gateway reads (tool_gateway.ownership_refusal), which
tests/test_browser_leases.py keeps equal; `lease_alive` reads only the run and generation a
container is labelled with. Nothing else of the service is imported, except types.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autobots.application.sql import SqlConnection
    from autobots.application.tool_definitions import ToolScope

# Run status and ownership, read fresh by database time, as tool_gateway.ownership_refusal reads it.
OWNERSHIP = (
    "select r.status as run_status, j.status as job_status, j.generation, "
    "j.lease_expires_at > clock_timestamp() as lease_live "
    "from public.runs r join app_private.run_jobs j on j.run_id = r.id "
    "where r.id = %s and r.workspace_id = %s"
)
# The run's job is claimed at the labelled generation with an unexpired lease, and the run runs.
GENERATION = (
    "select 1 from app_private.run_jobs j join public.runs r on r.id = j.run_id "
    "where j.run_id::text = %s and j.generation = %s and j.status = 'claimed' "
    "and j.lease_expires_at > clock_timestamp() and r.status = 'running'"
)


async def attempt_alive(connection: "SqlConnection", scope: "ToolScope") -> bool:
    """The attempt still owns a running run, by database time, as the gateway decides it."""
    cursor = await connection.execute(OWNERSHIP, (scope.run_id, scope.workspace_id))
    row = await cursor.fetchone()
    if row is None:
        return False
    run_status, job_status, generation, lease_live = row
    return (
        job_status == "claimed"
        and generation == scope.generation
        and bool(lease_live)
        and run_status == "running"
    )


def lease_alive(connection: "SqlConnection") -> Callable[[str, int], Awaitable[bool]]:
    """For the sweeper: a session lives only while its run's job is claimed at its generation."""

    async def alive(run_id: str, generation: int) -> bool:
        cursor = await connection.execute(GENERATION, (run_id, generation))
        return await cursor.fetchone() is not None

    return alive
