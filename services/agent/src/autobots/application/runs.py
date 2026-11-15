"""Run admission and transition commands, SP-010 and SP-014. Each commits with its event."""

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from autobots.application.model_admission import ACTIVE
from autobots.contracts.persisted import (
    AdmissionReceipt,
    PolicySnapshot,
    StoredEvent,
    StoredReceipt,
    TransitionReceipt,
    read_policy_snapshot,
)
from autobots.contracts.plans import GoalSpec, InputDocument, RequiredArtifact
from autobots.contracts.runs import RunStatusChanged
from autobots.domain.effects import ReceiptStatus
from autobots.domain.errors import FixedRefusal, RefusalKind
from autobots.domain.execution import current_contract
from autobots.domain.models import RolePolicy
from autobots.domain.runs import (
    INTERRUPTING,
    TERMINAL,
    Actor,
    CommandRefused,
    JobStatus,
    LockedJob,
    RunCommand,
    RunStatus,
    job_status_after,
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


async def append_event(connection: Any, run_id: UUID, payload: StoredEvent) -> int:
    """Sequences are gapless per run, and the row update serializes concurrent writers. Each
    payload is its public contract, built and validated by its writer in the write's transaction
    (refactor plan R-51), so what is stored is what `run_projection.project_event` shows."""
    cursor = await connection.execute(
        "update public.runs set event_sequence = event_sequence + 1 where id = %s "
        "returning event_sequence",
        (run_id,),
    )
    sequence: int = (await cursor.fetchone())[0]
    await connection.execute(
        "insert into public.run_events (run_id, sequence, schema_version, payload, occurred_at) "
        "values (%s, %s, 1, %s, now())",
        (run_id, sequence, json.dumps(payload.model_dump(mode="json"))),
    )
    return sequence


def _status_changed(previous: str, current: str) -> RunStatusChanged:
    return RunStatusChanged(
        type="run.status_changed", previous=RunStatus(previous), current=RunStatus(current)
    )


async def existing_receipt[T: StoredReceipt](
    connection: Any, scope: tuple[UUID, UUID, str, str, str], fingerprint: str, kind: type[T]
) -> T | None:
    """Serializes this exact key, so concurrent duplicates wait and then see the first result,
    read as `kind`, its operation's receipt (contracts/persisted.py). A stored result that can't be
    read raises, so a repeat never runs the operation again."""
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
    return kind.model_validate(row[1])


async def store_receipt(
    connection: Any,
    scope: tuple[UUID, UUID, str, str, str],
    fingerprint: str,
    result: StoredReceipt,
) -> None:
    await connection.execute(
        "insert into app_private.idempotency_receipts (workspace_id, actor_id, operation, target, "
        "idempotency_key, request_hash, result) values (%s, %s, %s, %s, %s, %s, %s)",
        (*scope, fingerprint, result.stored()),
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

    async def replayed[T: StoredReceipt](self, connection: Any, kind: type[T]) -> T | None:
        """The first result under this key, as its operation's receipt `kind`, inside the
        caller's transaction, or None."""
        return await existing_receipt(connection, self.scope, self.fingerprint, kind)

    async def store(self, connection: Any, result: StoredReceipt) -> None:
        await store_receipt(connection, self.scope, self.fingerprint, result)


# A run and every run below it, by parent, for a statement that continues `select ... from tree`.
RUN_TREE = (
    "with recursive tree as (select id from public.runs where id = %s union all "
    "select r.id from public.runs r join tree t on r.parent_run_id = t.id) "
)


async def require_run(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
    """Raises RunNotFound unless the run is this workspace's, as for a run that doesn't exist."""
    cursor = await connection.execute(
        "select 1 from public.runs where id = %s and workspace_id = %s", (run_id, workspace_id)
    )
    if await cursor.fetchone() is None:
        raise RunNotFound("that run is not available")


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


async def frozen_snapshot(connection: Any, run_id: UUID) -> PolicySnapshot:
    """The policy admission froze for this run, as stored (PolicySnapshot). A run with no row has
    nothing bound, and one whose snapshot can't be read raises UnknownModelProfile, so neither is
    routed on (refactor plan R-51, PRUN-08)."""
    cursor = await connection.execute(
        "select policy_snapshot from public.runs where id = %s", (run_id,)
    )
    row = await cursor.fetchone()
    return read_policy_snapshot({} if row is None else row[0])


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
    None here, so the insert takes its parent's, Decision 0015. A child stores its parent's
    snapshot document as it was read, older shapes included, so nothing a parent froze changes."""
    if isinstance(origin, Inherited):
        inherited = origin.inheritance
        return json.dumps(inherited.snapshot), inherited.parent_run_id, inherited.root_run_id, None
    return PolicySnapshot.of(origin.policy).stored(), None, None, origin.started_by


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
        existing = await existing_receipt(connection, scope, fingerprint, AdmissionReceipt)
        if existing is not None:
            return AdmissionResult(existing.run_id, existing.version, existing.status.value, True)
        await _require_continuable(connection, workspace_id, admission.continues_run_id)
        run_id = uuid4()
        status = RunStatus.QUEUED.value
        await _insert_run_and_job(connection, run_id, status, admission, goal)
        await _insert_inputs(connection, run_id, admission.input_documents)
        await _insert_goal_spec(connection, run_id, admission, request, goal, criteria)
        await append_event(connection, run_id, _status_changed(status, status))
        result = AdmissionReceipt(run_id=run_id, version=1, status=RunStatus.QUEUED)
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


async def apply_claim(connection: Any, run_id: UUID, current: RunStatus, version: int) -> RunStatus:
    """A claim's move, inside the claim's transaction under its job row lock: a queued run starts
    running by `claim` in the command table (SP-010). A run its last owner left in another state
    keeps it, and its new owner goes on from there."""
    if current is not RunStatus.QUEUED:
        return current
    following = next_status(current, RunCommand.CLAIM, Actor.WORKER) or current
    await record_transition(connection, run_id, current.value, following.value, version)
    return following


async def _has_unsettled_work(connection: Any, run_id: UUID) -> bool:
    """SP-010: straight to cancelled only with no attempt or effect still open. A call already
    classified uncertain stays recorded, and doesn't hold the run open."""
    cursor = await connection.execute(
        "select exists (select 1 from app_private.model_invocations where run_id = %s "
        "and status = any(%s)) or exists (select 1 from "
        "app_private.tool_receipts where run_id = %s and status = %s) "
        "or exists (select 1 from app_private.assignments where parent_run_id = %s "
        "and status = 'open')",
        (
            run_id,
            [status.value for status in ACTIVE],
            run_id,
            ReceiptStatus.STARTED.value,
            run_id,
        ),
    )
    return bool((await cursor.fetchone())[0])


async def _cancel_children(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
    """In the parent's transaction, so a cancel fences the whole tree at once. The system cancels
    each child, as no person asked for it (Decision 0029 F5)."""
    cursor = await connection.execute(
        "select id from public.runs where parent_run_id = %s and status <> all(%s)",
        (run_id, sorted(status.value for status in INTERRUPTING)),
    )
    for (child_id,) in await cursor.fetchall():
        await cascade_command(
            connection, workspace_id=workspace_id, run_id=child_id, command=RunCommand.CANCEL
        )


async def _withdraw_waits_and_cascade(connection: Any, workspace_id: UUID, run_id: UUID) -> None:
    """A cancel's side effects, in its transaction: pending requests are withdrawn, open waits are
    met, and the run's children are cancelled."""
    # Imported here: approvals imports this module for its run commands, so importing it at module
    # level would be circular. It stays the one writer of request status (Decision 0029 F8).
    from autobots.application.approvals import withdraw_pending

    await withdraw_pending(connection, run_id)
    # Nothing is waiting on an answer any more, so nothing can stay open against it.
    await connection.execute(
        "update app_private.run_obligations set status = 'met', response = 'cancelled', "
        "met_at = now() where run_id = %s and status = 'open'",
        (run_id,),
    )
    await _cancel_children(connection, workspace_id, run_id)


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


async def _lock_job(connection: Any, workspace_id: UUID, run_id: UUID) -> LockedJob:
    """The job's row lock, always before the run's, the same order a claim uses, so the two can't
    deadlock."""
    cursor = await connection.execute(
        "select status, generation, lease_expires_at > clock_timestamp() "
        "from app_private.run_jobs where run_id = %s and workspace_id = %s for update",
        (run_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return LockedJob(None, None, False)
    return LockedJob(JobStatus(row[0]), row[1], bool(row[2]))


async def _lock_run(connection: Any, workspace_id: UUID, run_id: UUID) -> tuple[RunStatus, int]:
    cursor = await connection.execute(
        "select status, version from public.runs where id = %s and workspace_id = %s for update",
        (run_id, workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        raise RunNotFound("that run is not available")
    return RunStatus(row[0]), int(row[1])


async def _write_job(
    connection: Any, run_id: UUID, status: JobStatus | None, *, resumed: bool
) -> None:
    """Under the job's row lock, in the transaction that moved the run."""
    if status is not None:
        await connection.execute(
            "update app_private.run_jobs set status = %s, lease_owner = null, "
            "lease_expires_at = null where run_id = %s",
            (status.value, run_id),
        )
    if resumed:
        # A resume starts the job's consecutive failed passes again from none (Decision 0028 E4).
        await connection.execute(
            "update app_private.run_jobs set failed_attempts = 0 where run_id = %s", (run_id,)
        )


async def _record_stop_reason(connection: Any, run_id: UUID, code: str | None) -> None:
    # A run can stop before its first segment, so the row may not exist yet.
    await connection.execute(
        "insert into app_private.run_usage (run_id, stop_reason) values (%s, %s) "
        "on conflict (run_id) do update set stop_reason = excluded.stop_reason",
        (run_id, code),
    )


class Unset(Enum):
    """A keyword left out, where None is one of the values it takes."""

    UNSET = "unset"


@dataclass(frozen=True)
class CommandReceipt:
    """A person's idempotency key for one command: who sent it, under which key. The two come
    together or not at all, so a receipt can't be skipped by passing one (SP-014, PRUN-06)."""

    actor_id: UUID
    idempotency_key: str


class WorkerClaim(Protocol):
    """A worker's hold on one run at one generation, such as a `Lease` or a tool call's scope."""

    @property
    def workspace_id(self) -> UUID: ...

    @property
    def run_id(self) -> UUID: ...

    @property
    def generation(self) -> int: ...


@dataclass(frozen=True)
class _Move:
    """One command as `_apply` takes it: on which run, by whom, at which version."""

    workspace_id: UUID
    run_id: UUID
    command: RunCommand
    actor: Actor
    expected_version: int
    generation: int | None = None
    receipt: Idempotent | None = None
    detail: str = ""
    response: str | None = None
    stop_reason: str | Literal[Unset.UNSET] | None = Unset.UNSET


async def _apply(connection: Any, move: _Move) -> TransitionResult:
    """Ownership, version, actor and SP-010 are checked where the change is written, and the
    change, its event, its job and its receipt commit together. Always the job's row, then the
    run's."""
    async with connection.transaction():
        if move.receipt is not None:
            existing = await move.receipt.replayed(connection, TransitionReceipt)
            if existing is not None:
                return TransitionResult(move.run_id, existing.version, existing.status.value, False)
        job = await _lock_job(connection, move.workspace_id, move.run_id)
        if move.actor is Actor.WORKER and (
            move.generation is None or not job.held_by(move.generation)
        ):
            raise LeaseLost("this worker no longer owns the run")
        current, version = await _lock_run(connection, move.workspace_id, move.run_id)
        has_active_work = job.live_claim or await _has_unsettled_work(connection, move.run_id)
        following = next_status(current, move.command, move.actor, has_active_work=has_active_work)
        if following is None:
            # Repeating a cancellation changes nothing, and is not a conflict.
            return TransitionResult(move.run_id, version, current.value, False)
        if version != move.expected_version:
            raise VersionConflict("the run changed; reload it")
        new_version = await record_transition(
            connection, move.run_id, current.value, following.value, version
        )
        await _record_obligation(connection, move.run_id, move.command, move.detail, move.response)
        if move.command is RunCommand.CANCEL:
            await _withdraw_waits_and_cascade(connection, move.workspace_id, move.run_id)
        await _write_job(
            connection,
            move.run_id,
            job_status_after(following, move.actor, job),
            resumed=move.command is RunCommand.RESUME,
        )
        if move.stop_reason is not Unset.UNSET:
            await _record_stop_reason(connection, move.run_id, move.stop_reason)
        if move.receipt is not None:
            await move.receipt.store(
                connection, TransitionReceipt(version=new_version, status=following)
            )
    return TransitionResult(move.run_id, new_version, following.value, True)


async def _version_of(connection: Any, run_id: UUID) -> int:
    """Read before the row locks, so a person's command that lands between this read and the locks
    is a version conflict."""
    cursor = await connection.execute("select version from public.runs where id = %s", (run_id,))
    row = await cursor.fetchone()
    if row is None:
        raise RunNotFound("that run is not available")
    return int(row[0])


async def apply_command(
    connection: Any,
    *,
    workspace_id: UUID,
    run_id: UUID,
    command: RunCommand,
    expected_version: int,
    receipt: CommandReceipt | None = None,
    response: str | None = None,
) -> TransitionResult:
    """A person's command at the version they saw (SP-010, SP-014). With a receipt, a repeat of its
    key replays the first result, and other content under it is refused."""
    idempotent = None
    if receipt is not None:
        idempotent = Idempotent.of(
            CommandKey(workspace_id, receipt.actor_id, receipt.idempotency_key),
            command.value,
            str(run_id),
            {"command": command.value, "expected_version": expected_version, "response": response},
        )
    return await _apply(
        connection,
        _Move(
            workspace_id,
            run_id,
            command,
            Actor.USER,
            expected_version,
            receipt=idempotent,
            response=response,
        ),
    )


async def apply_worker_command(
    connection: Any,
    claim: WorkerClaim,
    command: RunCommand,
    *,
    detail: str = "",
    stop_reason: str | Literal[Unset.UNSET] | None = Unset.UNSET,
) -> TransitionResult:
    """A command from the worker holding `claim`, fenced by its generation under the job's row
    lock (SP-010, SP-012). A stop reason, None included, commits with the transition, so a worker
    that lost the run writes neither."""
    version = await _version_of(connection, claim.run_id)
    return await _apply(
        connection,
        _Move(
            claim.workspace_id,
            claim.run_id,
            command,
            Actor.WORKER,
            version,
            generation=claim.generation,
            detail=detail,
            stop_reason=stop_reason,
        ),
    )


async def cascade_command(
    connection: Any, *, workspace_id: UUID, run_id: UUID, command: RunCommand
) -> TransitionResult:
    """A command neither a person nor the run's leased worker applies: a parent's cancel or resume
    reaching its child, a stray child's cancel, or an approval's expiry pausing its run. The system
    applies only cancel, pause and resume (Decision 0029 F5, SP-010)."""
    version = await _version_of(connection, run_id)
    return await _apply(connection, _Move(workspace_id, run_id, command, Actor.SYSTEM, version))


__all__ = [
    "RUN_TREE",
    "Actor",
    "AdmissionGrant",
    "CommandKey",
    "CommandReceipt",
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
    "TransitionResult",
    "Unset",
    "VersionConflict",
    "WorkerClaim",
    "admit",
    "admit_run",
    "ancestors_running",
    "append_event",
    "apply_claim",
    "apply_command",
    "apply_worker_command",
    "cascade_command",
    "current_status",
    "frozen_snapshot",
    "record_transition",
    "require_run",
]
