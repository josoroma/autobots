"""Deterministic completion, LC-12. A plausible answer can't mark a run successful."""

from dataclasses import dataclass
from uuid import UUID

from autobots.application.artifacts import (
    ArtifactUnavailable,
    ObjectStore,
    read_artifact,
    reconcile_run,
)
from autobots.application.plans import plan_view
from autobots.application.recovery import outstanding
from autobots.application.sql import SqlConnection, all_rows
from autobots.application.tool_definitions import ToolScope
from autobots.application.worker_leases import Lease
from autobots.contracts.plans import GoalSpec
from autobots.persistence.rows import NamedArtifactRow


@dataclass(frozen=True)
class VerificationReport:
    unmet: tuple[str, ...]
    # How many required artifacts were checked. Zero means nothing judged the content.
    checks: int

    @property
    def passed(self) -> bool:
        return not self.unmet


async def _latest_by_name(connection: SqlConnection, lease: Lease) -> dict[str, tuple[UUID, str]]:
    """The newest attempt per name decides, so an older good copy can't stand in for a lost one."""
    rows = await all_rows(
        connection,
        NamedArtifactRow,
        "select distinct on (name) name, id, status from public.artifacts where run_id = %s "
        "order by name, created_at desc",
        (lease.run_id,),
    )
    return {row.name: (row.id, row.status) for row in rows}


async def verify_candidate(
    connection: SqlConnection, store: ObjectStore | None, lease: Lease, goal: GoalSpec
) -> VerificationReport:
    """Reads back from storage. This writes no verdict: the owner records it with the transition."""
    unmet: list[str] = []
    view = await plan_view(connection, lease.run_id, goal)
    if not view.finished:
        unmet.append("plan_incomplete")
    left = await outstanding(connection, lease.run_id)
    if left.uncertain_calls:
        unmet.append("uncertain_model_call")
    if left.unknown_effects:
        unmet.append("unknown_effect")
    if store is None:
        return VerificationReport((*unmet, "storage_unavailable"), 0)
    owner = ToolScope(lease.workspace_id, lease.run_id, lease.generation, {})
    report = await reconcile_run(connection, store, lease.workspace_id, lease.run_id, owner)
    unmet.extend(f"artifact_incomplete:{name}" for name in report.incomplete)
    latest = await _latest_by_name(connection, lease)
    unmet.extend(
        f"artifact_missing:{name}"
        for name, (_, status) in sorted(latest.items())
        if status != "published" and f"artifact_incomplete:{name}" not in unmet
    )
    for required in goal.required_artifacts:
        found = latest.get(required.name)
        if found is None:
            unmet.append(f"artifact_missing:{required.name}")
            continue
        if found[1] != "published":
            continue
        try:
            _, _, content = await read_artifact(connection, store, lease.workspace_id, found[0])
        except ArtifactUnavailable:
            unmet.append(f"artifact_missing:{required.name}")
            continue
        text = content.decode(errors="replace")
        if not all(expected in text for expected in required.must_contain):
            unmet.append(f"artifact_check_failed:{required.name}")
    # With no stated requirement, a run still has to deliver something that exists.
    if not goal.required_artifacts and not any(s == "published" for _, s in latest.values()):
        unmet.append("no_published_artifact")
    return VerificationReport(tuple(dict.fromkeys(unmet)), len(goal.required_artifacts))
