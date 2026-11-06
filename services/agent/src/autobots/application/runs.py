"""Run admission and transition commands, SP-010 and SP-014. Each commits with its event."""

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from autobots.contracts.plans import GoalSpec, InputDocument, RequiredArtifact
from autobots.domain.execution import current_contract
from autobots.domain.models import PROFILES, RolePolicy
from autobots.domain.runs import (
    TERMINAL,
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


class LinkRefused(Exception):
    """Only a terminal run in this workspace can be continued."""

    code = "run_not_continuable"


class RunNotFound(Exception):
    """Also for a run in another workspace, so existence is not revealed."""

    code = "run_not_found"


@dataclass(frozen=True)
class Inheritance:
    """A child's admission: its parent's fixed policy, and scope already narrowed from it."""

    parent_run_id: UUID
    root_run_id: UUID
    snapshot: dict[str, Any]
    tools: dict[str, int]
    paths: tuple[str, ...]
    instructions: str
    session_id: UUID
    expert_id: UUID
    version: int


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


async def existing_receipt(
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


async def store_receipt(
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


def _snapshot(policy: RolePolicy | None) -> str:
    if policy is None:
        raise ValueError("a run needs a role policy or an inherited one")
    return json.dumps(
        {
            "version": policy.version,
            "bindings": {role.value: profile.value for role, profile in policy.bindings.items()},
            "routes": {
                profile.value: {
                    "wire_id": PROFILES[profile].wire_id,
                    "canonical_id": PROFILES[profile].canonical_id,
                }
                for profile in set(policy.bindings.values())
            },
        },
        sort_keys=True,
    )


async def _goal_to_repeat(connection: Any, workspace_id: UUID, run_id: UUID | None) -> str:
    """Whole, from what was stored, as anything shown on a page is cut and redacted."""
    cursor = await connection.execute(
        "select g.spec ->> 'original_request' from public.runs r "
        "join app_private.goal_specs g on g.run_id = r.id "
        "where r.id = %s and r.workspace_id = %s and r.parent_run_id is null and not exists "
        "(select 1 from public.workflow_executions e where e.run_id = r.id)",
        (run_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None or not row[0]:
        raise LinkRefused("only a goal run of its own, in this workspace, can repeat its goal")
    return str(row[0])


async def admit_run(
    connection: Any,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    idempotency_key: str,
    goal_text: str | None,
    limit_micro_usd: int,
    policy: RolePolicy | None = None,
    acceptance_criteria: tuple[str, ...] = (),
    continues_run_id: UUID | None = None,
    required_artifacts: tuple[RequiredArtifact, ...] = (),
    input_documents: tuple[InputDocument, ...] = (),
    binding: Any = None,
    inherit: Inheritance | None = None,
    run_profile: str | None = None,
) -> AdmissionResult:
    """Run, job and first event commit together. A repeat returns the original result."""
    if inherit is not None:
        binding = inherit
    if goal_text is None:
        goal_text = await _goal_to_repeat(connection, workspace_id, continues_run_id)
    goal = goal_text.strip()
    # With no stated criteria, the goal itself is the one thing to meet.
    criteria = [text.strip() for text in acceptance_criteria if text.strip()] or [goal]
    fingerprint = request_hash(
        {
            "goal_text": goal,
            "limit_micro_usd": limit_micro_usd,
            "criteria": criteria,
            "continues": str(continues_run_id),
            "required": [item.model_dump() for item in required_artifacts],
            "expert": [str(binding.expert_id), binding.version] if binding else None,
            "documents": [item.model_dump() for item in input_documents],
            # Only when chosen, so a receipt from before this field still matches.
            **({"run_profile": run_profile} if run_profile else {}),
        }
    )
    scope = (workspace_id, actor_id, "admit_run", str(workspace_id), idempotency_key)
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return AdmissionResult(
                UUID(existing["run_id"]), existing["version"], existing["status"], True
            )
        if continues_run_id is not None:
            cursor = await connection.execute(
                "select status from public.runs where id = %s and workspace_id = %s",
                (continues_run_id, workspace_id),
            )
            previous = await cursor.fetchone()
            if previous is None or RunStatus(previous[0]) not in TERMINAL:
                raise LinkRefused("only a terminal run in this workspace can be continued")
        run_id = uuid4()
        status = RunStatus.QUEUED.value
        await connection.execute(
            "insert into public.runs (id, workspace_id, status, limit_micro_usd, goal_text, "
            "goal_summary, version, policy_snapshot, continues_run_id, session_id, expert_id, "
            "expert_version, parent_run_id, root_run_id, execution_contract) "
            "values (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                run_id,
                workspace_id,
                status,
                limit_micro_usd,
                goal,
                goal[:200],
                json.dumps(inherit.snapshot) if inherit else _snapshot(policy),
                continues_run_id,
                binding.session_id if binding else None,
                binding.expert_id if binding else None,
                binding.version if binding else None,
                inherit.parent_run_id if inherit else None,
                inherit.root_run_id if inherit else None,
                json.dumps(current_contract()),
            ),
        )
        await connection.execute(
            "insert into app_private.run_jobs (run_id, workspace_id) values (%s, %s)",
            (run_id, workspace_id),
        )
        for document in input_documents:
            content = document.content
            await connection.execute(
                "insert into app_private.run_files (run_id, path, version, content, sha256, "
                "media_type, operation_id) values (%s, %s, 1, %s, %s, 'text/plain', %s)",
                (
                    run_id,
                    document.path,
                    content,
                    hashlib.sha256(content.encode()).hexdigest(),
                    f"input:{run_id}:{document.path}",
                ),
            )
        spec = GoalSpec(
            objective=goal,
            original_request=goal_text,
            criteria={f"c{index}": text for index, text in enumerate(criteria, start=1)},
            allowed_tools=dict(binding.tools) if binding else dict(LOOP_TOOL_GRANTS),
            instructions=binding.instructions if binding else "",
            allowed_paths=list(inherit.paths) if inherit else list(RUN_FILE_GRANTS),
            required_artifacts=list(required_artifacts),
        )
        await connection.execute(
            "insert into app_private.goal_specs (run_id, spec) values (%s, %s)",
            (run_id, spec.model_dump_json()),
        )
        await append_event(connection, run_id, _status_changed(status, status))
        result = {"run_id": str(run_id), "version": 1, "status": status}
        await store_receipt(connection, scope, fingerprint, result)
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


async def _has_unsettled_work(connection: Any, run_id: UUID) -> bool:
    """SP-010: straight to cancelled only with no attempt or effect still open. A call already
    classified uncertain stays recorded, and doesn't hold the run open."""
    cursor = await connection.execute(
        "select exists (select 1 from app_private.model_invocations where run_id = %s "
        "and status in ('reserved', 'dispatched')) or exists (select 1 from "
        "app_private.tool_receipts where run_id = %s and status = 'started') "
        "or exists (select 1 from app_private.assignments where parent_run_id = %s "
        "and status = 'open')",
        (run_id, run_id, run_id),
    )
    return bool((await cursor.fetchone())[0])


async def _cancel_children(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
    """In the parent's transaction, so a cancel fences the whole tree at once."""
    cursor = await connection.execute(
        "select id, version from public.runs where parent_run_id = %s "
        "and status not in ('succeeded', 'failed', 'cancelled', 'cancelling')",
        (run_id,),
    )
    for child_id, version in await cursor.fetchall():
        await apply_command(
            connection,
            workspace_id=workspace_id,
            run_id=child_id,
            command=RunCommand.CANCEL,
            actor=Actor.USER,
            expected_version=version,
        )


async def _record_obligation(
    connection: Any, run_id: UUID, command: RunCommand, detail: str, response: str | None
) -> None:
    """A wait outlives a pause, so a resume can't skip what it was waiting for."""
    kinds = {RunCommand.REQUEST_INPUT: "input", RunCommand.REQUEST_APPROVAL: "approval"}
    answers = {RunCommand.SUBMIT_INPUT: "input", RunCommand.DECIDE_APPROVAL: "approval"}
    if command in kinds:
        await connection.execute(
            "insert into app_private.run_obligations (id, run_id, kind, detail) "
            "values (%s, %s, %s, %s) "
            "on conflict (run_id, kind) where status = 'open' do nothing",
            (uuid4(), run_id, kinds[command], detail),
        )
    elif command in answers:
        await connection.execute(
            "update app_private.run_obligations set status = 'met', response = %s, met_at = now() "
            "where run_id = %s and kind = %s and status = 'open'",
            (response, run_id, answers[command]),
        )


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
    detail: str = "",
    response: str | None = None,
) -> TransitionResult:
    """Ownership, version, actor and SP-010 are checked where the change is written.

    Always the job's row, then the run's, the same order a claim uses, so the two can't deadlock.
    """
    fingerprint = request_hash(
        {"command": command.value, "expected_version": expected_version, "response": response}
    )
    scope = None
    if actor_id is not None and idempotency_key is not None:
        scope = (workspace_id, actor_id, command.value, str(run_id), idempotency_key)
    async with connection.transaction():
        if scope is not None:
            existing = await existing_receipt(connection, scope, fingerprint)
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
        has_active_work = (job is not None and job[0] == "claimed" and bool(job[2])) or (
            await _has_unsettled_work(connection, run_id)
        )
        following = next_status(current, command, actor, has_active_work=has_active_work)
        if following is None:
            # Repeating a cancellation changes nothing, and is not a conflict.
            return TransitionResult(run_id, version, current.value, False)
        if version != expected_version:
            raise VersionConflict("the run changed; reload it")
        new_version = await record_transition(
            connection, run_id, current.value, following.value, version
        )
        await _record_obligation(connection, run_id, command, detail, response)
        if command is RunCommand.CANCEL:
            await connection.execute(
                "update public.approval_requests set status = 'withdrawn' "
                "where run_id = %s and status = 'pending'",
                (run_id,),
            )
            # Nothing is waiting on an answer any more, so nothing can stay open against it.
            await connection.execute(
                "update app_private.run_obligations set status = 'met', response = 'cancelled', "
                "met_at = now() where run_id = %s and status = 'open'",
                (run_id,),
            )
            await _cancel_children(connection, workspace_id, run_id)
        job_status = _job_status(following)
        if following is RunStatus.CANCELLING and not (
            job is not None and job[0] == "claimed" and bool(job[2])
        ):
            # Open work with no live owner. Something has to come back and settle it.
            job_status = "queued"
        if (
            following is RunStatus.PAUSED
            and actor is Actor.USER
            and job is not None
            and job[0] == "claimed"
            and bool(job[2])
        ):
            # The owner sees this at its next check, saves its step and lets go.
            job_status = None
        if job_status is not None:
            await connection.execute(
                "update app_private.run_jobs set status = %s, lease_owner = null, "
                "lease_expires_at = null where run_id = %s",
                (job_status, run_id),
            )
        result = {"version": new_version, "status": following.value}
        if scope is not None:
            await store_receipt(connection, scope, fingerprint, result)
    return TransitionResult(run_id, new_version, following.value, True)


__all__ = [
    "Actor",
    "CommandRefused",
    "IdempotencyConflict",
    "Inheritance",
    "LeaseLost",
    "LinkRefused",
    "RunNotFound",
    "VersionConflict",
    "admit_run",
    "append_event",
    "apply_command",
    "record_transition",
]
