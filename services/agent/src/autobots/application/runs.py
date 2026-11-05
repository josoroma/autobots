"""Run admission and transition commands, SP-010 and SP-014. Each commits with its event."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.contracts.plans import GoalSpec
from autobots.domain.models import RolePolicy
from autobots.domain.runs import (
    Actor,
    CommandRefused,
    RunCommand,
    RunStatus,
    next_status,
)
from autobots.domain.tools import LOOP_TOOL_GRANTS, RUN_FILE_GRANTS


class IdempotencyConflict(Exception):
    """The same key with different content. Nothing is created or changed."""

    code = "idempotency_conflict"


class VersionConflict(Exception):
    code = "version_conflict"


class LeaseLost(Exception):
    """This worker's generation isn't current any more, so it may write nothing."""

    code = "lease_lost"


class RunNotFound(Exception):
    """Also for a run in another workspace, so existence is not revealed."""

    code = "run_not_found"


@dataclass(frozen=True)
class AdmissionResult:
    run_id: UUID
    version: int
    status: str
    replayed: bool


def request_hash(payload: dict[str, Any]) -> str:
    """Over normalized content, so key order and whitespace around the goal don't differ."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


async def append_event(connection: Any, run_id: UUID, payload: dict[str, Any]) -> int:
    """Sequences are gapless per run, and the row update serializes concurrent writers."""
    cursor = await connection.execute(
        "update public.runs set event_sequence = event_sequence + 1 where id = %s "
        "returning event_sequence",
        (run_id,),
    )
    sequence: int = (await cursor.fetchone())[0]
    await connection.execute(
        "insert into public.run_events (run_id, sequence, schema_version, payload, occurred_at) "
        "values (%s, %s, 1, %s, now())",
        (run_id, sequence, json.dumps(payload)),
    )
    return sequence


def _status_changed(previous: str, current: str) -> dict[str, str]:
    return {"type": "run.status_changed", "previous": previous, "current": current}


async def _existing_receipt(
    connection: Any, scope: tuple[UUID, UUID, str, str, str], fingerprint: str
) -> dict[str, Any] | None:
    """Serializes this exact key, so concurrent duplicates wait and then see the first result."""
    await connection.execute(
        "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
        ("|".join(str(part) for part in scope),),
    )
    cursor = await connection.execute(
        "select request_hash, result from app_private.idempotency_receipts where "
        "workspace_id = %s and actor_id = %s and operation = %s and target = %s "
        "and idempotency_key = %s",
        scope,
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    if row[0] != fingerprint:
        raise IdempotencyConflict("this key was used with different content")
    result: dict[str, Any] = row[1]
    return result


async def _store_receipt(
    connection: Any,
    scope: tuple[UUID, UUID, str, str, str],
    fingerprint: str,
    result: dict[str, Any],
) -> None:
    await connection.execute(
        "insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, "
        "idempotency_key, request_hash, result) values (%s, %s, %s, %s, %s, %s, %s)",
        (*scope, fingerprint, json.dumps(result)),
    )


def _snapshot(policy: RolePolicy) -> str:
    return json.dumps(
        {
            "version": policy.version,
            "bindings": {role.value: profile.value for role, profile in policy.bindings.items()},
        },
        sort_keys=True,
    )


async def admit_run(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    goal_text: str,
    limit_micro_usd: int,
    policy: RolePolicy,
    acceptance_criteria: tuple[str, ...] = (),
) -> AdmissionResult:
    """Run, job and first event commit together. A repeat returns the original result."""
    goal = goal_text.strip()
    # With no stated criteria, the goal itself is the one thing to meet.
    criteria = [text.strip() for text in acceptance_criteria if text.strip()] or [goal]
    fingerprint = request_hash(
        {"goal_text": goal, "limit_micro_usd": limit_micro_usd, "criteria": criteria}
    )
    scope = (workspace_id, actor_id, "admit_run", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await _existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return AdmissionResult(
                UUID(existing["run_id"]), existing["version"], existing["status"], True
            )
        run_id = uuid4()
        status = RunStatus.QUEUED.value
        await connection.execute(
            "insert into public.runs (id, workspace_id, status, limit_micro_usd, goal_text, "
            "goal_summary, version, policy_snapshot) values (%s, %s, %s, %s, %s, %s, 1, %s)",
            (
                run_id,
                workspace_id,
                status,
                limit_micro_usd,
                goal,
                goal[:200],
                _snapshot(policy),
            ),
        )
        await connection.execute(
            "insert into app_private.run_jobs (run_id, workspace_id) values (%s, %s)",
            (run_id, workspace_id),
        )
        spec = GoalSpec(
            objective=goal,
            original_request=goal_text,
            criteria={f"c{index}": text for index, text in enumerate(criteria, start=1)},
            allowed_tools=dict(LOOP_TOOL_GRANTS),
            allowed_paths=list(RUN_FILE_GRANTS),
        )
        await connection.execute(
            "insert into app_private.goal_specs (run_id, spec) values (%s, %s)",
            (run_id, spec.model_dump_json()),
        )
        await append_event(connection, run_id, _status_changed(status, status))
        result = {"run_id": str(run_id), "version": 1, "status": status}
        await _store_receipt(connection, scope, fingerprint, result)
    return AdmissionResult(run_id, 1, status, False)


def _job_status(following: RunStatus) -> str | None:
    """What a transition does to the job. A run that isn't waiting for a worker can't be claimed."""
    if following is RunStatus.QUEUED:
        return "queued"
    if following in {RunStatus.RUNNING, RunStatus.VERIFYING, RunStatus.CANCELLING}:
        return None  # The worker holding the lease still owns it.
    return "done"


@dataclass(frozen=True)
class TransitionResult:
    run_id: UUID
    version: int
    status: str
    changed: bool


async def record_transition(
    connection: Any, run_id: UUID, previous: str, following: str, version: int
) -> int:
    """The status, its version and its event, always together."""
    new_version = version + 1
    await connection.execute(
        "update public.runs set status = %s, version = %s, updated_at = now() where id = %s",
        (following, new_version, run_id),
    )
    await append_event(connection, run_id, _status_changed(previous, following))
    return new_version


def _require_owner(job: Any, generation: int | None) -> None:
    """Checked under the job's row lock, in the transaction that makes the change."""
    if generation is None or job is None:
        raise LeaseLost("this worker no longer owns the run")
    status, current, live = job
    if status != "claimed" or current != generation or not live:
        raise LeaseLost("this worker no longer owns the run")


async def apply_command(
    connection: Any,
    *,
    workspace_id: UUID,
    run_id: UUID,
    command: RunCommand,
    actor: Actor,
    expected_version: int,
    generation: int | None = None,
    actor_id: UUID | None = None,
    idempotency_key: str | None = None,
) -> TransitionResult:
    """Ownership, version, actor and SP-010 are checked where the change is written.

    Always the job's row, then the run's, the same order a claim uses, so the two can't deadlock.
    """
    fingerprint = request_hash({"command": command.value, "expected_version": expected_version})
    scope = None
    if actor_id is not None and idempotency_key is not None:
        scope = (workspace_id, actor_id, command.value, str(run_id), idempotency_key)
    async with connection.transaction():
        if scope is not None:
            existing = await _existing_receipt(connection, scope, fingerprint)
            if existing is not None:
                return TransitionResult(run_id, existing["version"], existing["status"], False)
        cursor = await connection.execute(
            "select status, generation, lease_expires_at > clock_timestamp() "
            "from app_private.run_jobs where run_id = %s and workspace_id = %s for update",
            (run_id, workspace_id),
        )
        job = await cursor.fetchone()
        if actor is Actor.WORKER:
            _require_owner(job, generation)
        cursor = await connection.execute(
            "select status, version from public.runs "
            "where id = %s and workspace_id = %s for update",
            (run_id, workspace_id),
        )
        row = await cursor.fetchone()
        if row is None:
            raise RunNotFound("that run is not available")
        current, version = RunStatus(row[0]), row[1]
        has_active_work = job is not None and job[0] == "claimed" and bool(job[2])
        following = next_status(current, command, actor, has_active_work=has_active_work)
        if following is None:
            # Repeating a cancellation changes nothing, and is not a conflict.
            return TransitionResult(run_id, version, current.value, False)
        if version != expected_version:
            raise VersionConflict("the run changed; reload it")
        new_version = await record_transition(
            connection, run_id, current.value, following.value, version
        )
        job_status = _job_status(following)
        if job_status is not None:
            await connection.execute(
                "update app_private.run_jobs set status = %s, lease_owner = null, "
                "lease_expires_at = null where run_id = %s",
                (job_status, run_id),
            )
        result = {"version": new_version, "status": following.value}
        if scope is not None:
            await _store_receipt(connection, scope, fingerprint, result)
    return TransitionResult(run_id, new_version, following.value, True)


__all__ = [
    "CommandRefused",
    "IdempotencyConflict",
    "LeaseLost",
    "RunNotFound",
    "VersionConflict",
    "admit_run",
    "append_event",
    "apply_command",
    "record_transition",
]
