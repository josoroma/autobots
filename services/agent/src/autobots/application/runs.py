"""Run admission and transition commands, SP-010 and SP-014. Each commits with its event."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from autobots.contracts.plans import GoalSpec, InputDocument, RequiredArtifact
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.execution import current_contract
from autobots.domain.models import PROFILES, RolePolicy
from autobots.domain.runs import (
    INTERRUPTING,
    TERMINAL,
    Actor,
    CommandRefused,
    RunCommand,
    RunStatus,
    next_status,
)
from autobots.domain.tools import LOOP_TOOL_GRANTS, RUN_FILE_GRANTS


class IdempotencyConflict(FixedRefusal):
    """The same key with different content. Nothing is created or changed."""

    code = "idempotency_conflict"


class VersionConflict(FixedRefusal):
    code = "version_conflict"


class LeaseLost(Exception):
    """This worker's generation isn't current any more, so it may write nothing."""

    code = "lease_lost"


class LinkRefused(FixedRefusal):
    """Only a terminal run in this workspace can be continued."""

    code = "run_not_continuable"


class RunNotFound(FixedRefusal):
    """Also for a run in another workspace, so existence is not revealed."""

    code = "run_not_found"
    kind = RefusalKind.NOT_FOUND


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


class AdmissionGrant(Protocol):
    """What a run is granted at admission: its tools and instructions, and the session and Expert
    revision they came from. RunBinding, Inheritance and RunGrant satisfy it structurally, so they
    stay distinct types (refactor plan R-30, PPRD-01)."""

    @property
    def session_id(self) -> UUID | None: ...

    @property
    def expert_id(self) -> UUID | None: ...

    @property
    def version(self) -> int | None: ...

    @property
    def instructions(self) -> str: ...

    @property
    def tools(self) -> Mapping[str, int]: ...


@dataclass(frozen=True)
class RunGrant:
    """A grant its caller builds with no session to resolve: a routine's Expert run, a workflow's
    run, a held-out replay or a trial."""

    instructions: str
    tools: Mapping[str, int]
    session_id: UUID | None = None
    expert_id: UUID | None = None
    version: int | None = None


@dataclass(frozen=True)
class Fresh:
    """A run of its own. It freezes this role policy, and its grant, or the default loop's if None.

    `started_by` is the person who started it, never the actor, which can be a routine. A routine's
    run has none, Decision 0015.
    """

    policy: RolePolicy
    grant: AdmissionGrant | None = None
    started_by: UUID | None = None


@dataclass(frozen=True)
class Inherited:
    """A child. It takes its parent's frozen policy and started_by (Decision 0015), and its grant is
    the inheritance itself."""

    inheritance: Inheritance

    @property
    def grant(self) -> AdmissionGrant:
        return self.inheritance


@dataclass(frozen=True)
class RunAdmission:
    """One request to admit a run. Its origin is a policy unless inherited, as a type (PRUN-04).

    A `goal_text` of None repeats the goal of `continues_run_id`.
    """

    workspace_id: UUID
    actor_id: UUID
    idempotency_key: str
    goal_text: str | None
    limit_micro_usd: int
    origin: Fresh | Inherited
    acceptance_criteria: tuple[str, ...] = ()
    continues_run_id: UUID | None = None
    required_artifacts: tuple[RequiredArtifact, ...] = ()
    input_documents: tuple[InputDocument, ...] = ()
    run_profile: str | None = None


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


@dataclass(frozen=True)
class CommandKey:
    """Who sent a command, in which workspace, under which idempotency key (PTOL-15)."""

    workspace_id: UUID
    actor_id: UUID
    idempotency_key: str


@dataclass(frozen=True)
class Idempotent:
    """One command's idempotency receipt: its key's scope for an operation and target, and the
    fingerprint of what it asked. A repeat with the same content replays the stored result, and
    one with other content is refused (`existing_receipt`). Commands share this skeleton, built by
    `of`, so none rebuilds the scope or fingerprint by hand (PTOL-15)."""

    scope: tuple[UUID, UUID, str, str, str]
    fingerprint: str

    @classmethod
    def of(
        cls, key: CommandKey, operation: str, target: str, payload: dict[str, Any]
    ) -> "Idempotent":
        scope = (key.workspace_id, key.actor_id, operation, target, key.idempotency_key)
        return cls(scope, request_hash(payload))

    async def replayed(self, connection: Any) -> dict[str, Any] | None:
        """The first result under this key, inside the caller's transaction, or None."""
        return await existing_receipt(connection, self.scope, self.fingerprint)

    async def store(self, connection: Any, result: dict[str, Any]) -> None:
        await store_receipt(connection, self.scope, self.fingerprint, result)


# A run and every run below it, by parent, for a statement that continues `select ... from tree`.
RUN_TREE = (
    "with recursive tree as (select id from public.runs where id = %s union all "
    "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
)


async def current_status(connection: Any, run_id: UUID) -> RunStatus | None:
    """The run's status now, or None when there is no such run."""
    cursor = await connection.execute("select status from public.runs where id = %s", (run_id,))
    row = await cursor.fetchone()
    return None if row is None else RunStatus(row[0])


async def ancestors_running(connection: Any, parent_run_id: UUID) -> bool:
    """Whether a child's parent and every run above it are running, so the child may go on."""
    cursor = await connection.execute(
        "with recursive up as (select id, parent_run_id, status from public.runs "
        "where id = %s union all select r.id, r.parent_run_id, r.status "
        "from public.runs r join up u on r.id = u.parent_run_id) "
        "select count(*) from up where status <> %s",
        (parent_run_id, RunStatus.RUNNING.value),
    )
    return not (await cursor.fetchone())[0]


def _snapshot(policy: RolePolicy) -> str:
    return json.dumps(
        {
            "version": policy.version,
            "bindings": {role.value: profile.value for role, profile in policy.bindings.items()},
            # Where each binding came from, PRD-Studio MD-02. Older snapshots have none.
            "sources": {role.value: source.value for role, source in policy.sources.items()},
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


def _fingerprint(admission: RunAdmission, goal: str, criteria: list[str]) -> str:
    """The receipt's request hash. Its payload stays byte-identical, or stored receipts stop
    replaying: tests/test_run_admission.py holds each caller shape's golden digest (R-30)."""
    grant = admission.origin.grant
    return request_hash(
        {
            "goal_text": goal,
            "limit_micro_usd": admission.limit_micro_usd,
            "criteria": criteria,
            "continues": str(admission.continues_run_id),
            "required": [item.model_dump() for item in admission.required_artifacts],
            "expert": [str(grant.expert_id), grant.version] if grant is not None else None,
            # The media type only when chosen, so a receipt from before that field still matches.
            "documents": [
                item.model_dump(exclude={"media_type"} if item.media_type == "text/plain" else None)
                for item in admission.input_documents
            ],
            # Only when chosen, so a receipt from before this field still matches.
            **({"run_profile": admission.run_profile} if admission.run_profile else {}),
        }
    )


async def _require_continuable(connection: Any, workspace_id: UUID, run_id: UUID | None) -> None:
    if run_id is None:
        return
    cursor = await connection.execute(
        "select status from public.runs where id = %s and workspace_id = %s",
        (run_id, workspace_id),
    )
    previous = await cursor.fetchone()
    if previous is None or RunStatus(previous[0]) not in TERMINAL:
        raise LinkRefused("only a terminal run in this workspace can be continued")


def _lineage(origin: Fresh | Inherited) -> tuple[str, UUID | None, UUID | None, UUID | None]:
    """The policy snapshot, parent, root and started_by a run row records. A child's started_by is
    None here, so the insert takes its parent's, Decision 0015."""
    if isinstance(origin, Inherited):
        inherited = origin.inheritance
        return json.dumps(inherited.snapshot), inherited.parent_run_id, inherited.root_run_id, None
    return _snapshot(origin.policy), None, None, origin.started_by


async def _insert_run_and_job(
    connection: Any, run_id: UUID, status: str, admission: RunAdmission, goal: str
) -> None:
    snapshot, parent, root, started_by = _lineage(admission.origin)
    grant = admission.origin.grant
    await connection.execute(
        "insert into public.runs (id, workspace_id, status, limit_micro_usd, goal_text, "
        "goal_summary, version, policy_snapshot, continues_run_id, session_id, expert_id, "
        "expert_version, parent_run_id, root_run_id, execution_contract, started_by) "
        "values (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s, %s, %s, %s, %s, "
        "coalesce(%s, (select started_by from public.runs where id = %s)))",
        (
            run_id,
            admission.workspace_id,
            status,
            admission.limit_micro_usd,
            goal,
            goal[:200],
            snapshot,
            admission.continues_run_id,
            grant.session_id if grant is not None else None,
            grant.expert_id if grant is not None else None,
            grant.version if grant is not None else None,
            parent,
            root,
            json.dumps(current_contract()),
            started_by,
            parent,
        ),
    )
    await connection.execute(
        "insert into app_private.run_jobs (run_id, workspace_id) values (%s, %s)",
        (run_id, admission.workspace_id),
    )


async def _insert_inputs(
    connection: Any, run_id: UUID, documents: tuple[InputDocument, ...]
) -> None:
    for document in documents:
        content = document.content
        await connection.execute(
            "insert into app_private.run_files (run_id, path, version, content, sha256, "
            "media_type, operation_id) values (%s, %s, 1, %s, %s, %s, %s)",
            (
                run_id,
                document.path,
                content,
                hashlib.sha256(content.encode()).hexdigest(),
                document.media_type,
                f"input:{run_id}:{document.path}",
            ),
        )


async def _insert_goal_spec(
    connection: Any,
    run_id: UUID,
    admission: RunAdmission,
    request: str,
    goal: str,
    criteria: list[str],
) -> None:
    """Tools, instructions and paths come from the grant, or the default loop's with none."""
    origin = admission.origin
    grant = origin.grant
    spec = GoalSpec(
        objective=goal,
        original_request=request,
        criteria={f"c{index}": text for index, text in enumerate(criteria, start=1)},
        allowed_tools=dict(grant.tools) if grant is not None else dict(LOOP_TOOL_GRANTS),
        instructions=grant.instructions if grant is not None else "",
        allowed_paths=(
            list(origin.inheritance.paths)
            if isinstance(origin, Inherited)
            else list(RUN_FILE_GRANTS)
        ),
        required_artifacts=list(admission.required_artifacts),
    )
    await connection.execute(
        "insert into app_private.goal_specs (run_id, spec) values (%s, %s)",
        (run_id, spec.model_dump_json()),
    )


async def admit(connection: Any, admission: RunAdmission) -> AdmissionResult:
    """Run, job, inputs, goal, first event and receipt commit together, SP-014. A repeat of the key
    with the same content returns the original result, and with other content is refused."""
    workspace_id = admission.workspace_id
    request = admission.goal_text
    if request is None:
        request = await _goal_to_repeat(connection, workspace_id, admission.continues_run_id)
    goal = request.strip()
    # With no stated criteria, the goal itself is the one thing to meet.
    criteria = [text.strip() for text in admission.acceptance_criteria if text.strip()] or [goal]
    fingerprint = _fingerprint(admission, goal, criteria)
    scope = (
        workspace_id,
        admission.actor_id,
        "admit_run",
        str(workspace_id),
        admission.idempotency_key,
    )
    async with connection.transaction():
        existing = await existing_receipt(connection, scope, fingerprint)
        if existing is not None:
            return AdmissionResult(
                UUID(existing["run_id"]), existing["version"], existing["status"], True
            )
        await _require_continuable(connection, workspace_id, admission.continues_run_id)
        run_id = uuid4()
        status = RunStatus.QUEUED.value
        await _insert_run_and_job(connection, run_id, status, admission, goal)
        await _insert_inputs(connection, run_id, admission.input_documents)
        await _insert_goal_spec(connection, run_id, admission, request, goal, criteria)
        await append_event(connection, run_id, _status_changed(status, status))
        result = {"run_id": str(run_id), "version": 1, "status": status}
        await store_receipt(connection, scope, fingerprint, result)
    return AdmissionResult(run_id, 1, status, False)


async def admit_run(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
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
    binding: AdmissionGrant | None = None,
    inherit: Inheritance | None = None,
    run_profile: str | None = None,
    started_by: UUID | None = None,
) -> AdmissionResult:
    """`admit` by keywords, as the database checks call it. An inheritance makes a child, which
    ignores `binding`, `policy` and `started_by` and takes its parent's, Decision 0015."""
    origin: Fresh | Inherited
    if inherit is not None:
        origin = Inherited(inherit)
    elif policy is not None:
        origin = Fresh(policy, binding, started_by)
    else:
        raise ValueError("a run needs a role policy or an inherited one")
    return await admit(
        connection,
        RunAdmission(
            workspace_id=workspace_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            goal_text=goal_text,
            limit_micro_usd=limit_micro_usd,
            origin=origin,
            acceptance_criteria=acceptance_criteria,
            continues_run_id=continues_run_id,
            required_artifacts=required_artifacts,
            input_documents=input_documents,
            run_profile=run_profile,
        ),
    )


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
        "select id, version from public.runs where parent_run_id = %s and status <> all(%s)",
        (run_id, sorted(INTERRUPTING)),
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


async def apply_command(  # noqa: PLR0913 - baseline 2026-11-14, shrink only (STD-06)
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
            # Imported here: approvals imports this module for its run commands, so importing it
            # at module level would be circular. It stays the one writer of request status.
            from autobots.application.approvals import withdraw_pending

            await withdraw_pending(connection, run_id)
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
        if command is RunCommand.RESUME:
            # A person's resume starts the job's consecutive failed passes again from none
            # (Decision 0028 E4).
            await connection.execute(
                "update app_private.run_jobs set failed_attempts = 0 where run_id = %s", (run_id,)
            )
        result = {"version": new_version, "status": following.value}
        if scope is not None:
            await store_receipt(connection, scope, fingerprint, result)
    return TransitionResult(run_id, new_version, following.value, True)


__all__ = [
    "RUN_TREE",
    "Actor",
    "AdmissionGrant",
    "CommandKey",
    "CommandRefused",
    "Fresh",
    "IdempotencyConflict",
    "Idempotent",
    "Inheritance",
    "Inherited",
    "LeaseLost",
    "LinkRefused",
    "RunAdmission",
    "RunGrant",
    "RunNotFound",
    "VersionConflict",
    "admit",
    "admit_run",
    "ancestors_running",
    "append_event",
    "apply_command",
    "current_status",
    "record_transition",
]
