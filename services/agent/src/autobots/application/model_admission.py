"""Slots and spend, MP-07. Admission happens under a workspace lock, before any provider call."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from autobots.application.sql import SqlConnection, required_row
from autobots.persistence.rows import LedgerUsageRow, SpendLimitsRow


class InvocationStatus(StrEnum):
    """A model call's ledger row, apart from its run's status (SP-008, SP-010). This module is its
    only writer."""

    RESERVED = "reserved"
    DISPATCHED = "dispatched"
    SUCCEEDED = "succeeded"
    FAILED_BEFORE_ACCEPTANCE = "failed_before_acceptance"
    UNCERTAIN = "uncertain"
    CANCELLED = "cancelled"


class SettlementReason(StrEnum):
    """Why the ledger closed a call, or left its cost open, where no provider failure says: kept
    in `failure_class` beside `model_attempts.FailureClass` (PRUN-09)."""

    # Its worker died: one never sent costs nothing, and one sent may have happened.
    WORKER_LOST = "worker_lost"
    CANCELLED = "cancelled"
    CANCELLED_AFTER_DISPATCH = "cancelled_after_dispatch"
    # The call worked and the provider named no charge, so only the amount is open.
    CHARGE_NOT_REPORTED = "charge_not_reported"


# What still holds a slot. A settled or uncertain attempt no longer does.
ACTIVE = (InvocationStatus.RESERVED, InvocationStatus.DISPATCHED)
# What still counts against a budget, in full, because its cost isn't settled.
OUTSTANDING = (*ACTIVE, InvocationStatus.UNCERTAIN)
# The ledger's column default, for a workspace whose limits row doesn't exist yet.
DEFAULT_DAILY_LIMIT_MICRO_USD = 5_000_000
WARNING_PERCENT = 80


class AdmissionRefused(Exception):
    code = "admission_refused"


class BudgetExceeded(AdmissionRefused):
    """New paid admission pauses. Nothing is dispatched, and the work is preserved."""

    code = "budget_exceeded"


class NoInferenceSlot(AdmissionRefused):
    code = "no_inference_slot"


class CostUnavailable(AdmissionRefused):
    """Unknown or unbounded pricing blocks a paid call, MP-07."""

    code = "cost_unavailable"


class AttemptAlreadySettled(ValueError):
    """Recovery settled or closed this attempt while it was out, so this step changes nothing. Also
    a ValueError, which tests/db/admission_check.py and verification_check.py catch (refactor plan
    R-41, PRUN-13)."""


@dataclass(frozen=True)
class ReplyFacts:
    """A reply's own account of itself, with no message content."""

    finish_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    tool_names: tuple[str, ...]
    invalid_tool_calls: int


@dataclass(frozen=True)
class Pricing:
    """Micro-dollars per million tokens, and per request. Include billable reasoning in output."""

    input_per_million: int
    output_per_million: int
    per_request: int = 0
    # Where a higher rate starts, past the prompt size these rates assume.
    tier_from_tokens: int | None = None


def worst_case_cost(pricing: Pricing | None, input_tokens: int, max_output_tokens: int) -> int:
    """Rounded up, so a reservation never under-counts."""
    if (
        pricing is None
        or min(pricing.input_per_million, pricing.output_per_million, pricing.per_request) < 0
    ):
        raise CostUnavailable("this model's price is not known")
    usage = (
        input_tokens * pricing.input_per_million + max_output_tokens * pricing.output_per_million
    )
    return (usage + 999_999) // 1_000_000 + pricing.per_request


@dataclass(frozen=True)
class AdmissionRequest:
    workspace_id: UUID
    root_run_id: UUID
    run_id: UUID
    role: str
    profile: str
    wire_id: str
    attempt: int
    worst_case_micro_usd: int
    credential_version: int | None = None


@dataclass(frozen=True)
class Ticket:
    invocation_id: UUID
    reserved_micro_usd: int
    warning: bool
    run_percent: int
    workspace_percent: int


def _percent(used: int, limit: int) -> int:
    return 100 if limit <= 0 else used * 100 // limit


def _values(statuses: tuple[InvocationStatus, ...]) -> list[str]:
    return [status.value for status in statuses]


# The ledger's spend, defined once and shared by admission, the run projection and the workflow
# overview (Decision 0029 F10, PRUN-09, XDUP-05). Each fragment takes the ledger's table alias, or
# none. A statement using them binds LEDGER_PARAMS.
LEDGER_PARAMS: dict[str, list[str]] = {"outstanding": _values(OUTSTANDING)}


def _column(alias: str, name: str) -> str:
    return f"{alias}.{name}" if alias else name


def cost_open(alias: str = "") -> str:
    """Whether a row's cost is still open, so its reservation counts rather than a charge."""
    return f"{_column(alias, 'status')} = any(%(outstanding)s)"


def reservation(alias: str = "") -> str:
    return _column(alias, "reserved_micro_usd")


def charge(alias: str = "") -> str:
    return f"coalesce({_column(alias, 'charged_micro_usd')}, 0)"


def spend(alias: str = "") -> str:
    """What one row counts against a budget: its reservation while its cost is open, and its
    reported charge once settled (MP-07)."""
    return f"case when {cost_open(alias)} then {reservation(alias)} else {charge(alias)} end"


def under_root(root: str, alias: str = "") -> str:
    """The rows a root's budget counts: every call whose root is `root`, its own and every
    descendant's, as admission scopes them (SP-008)."""
    return f"{_column(alias, 'root_run_id')} = {root}"


def shown_for(run: str, alias: str = "i") -> str:
    """The rows a run's own figures show, for a `public.runs` row aliased `run`: its root's, as
    admission counts them, and for a child, which no budget is scoped by, the calls it made itself
    (US-11.12 N-9, Decision 0029 F10)."""
    return (
        f"({under_root(f'{run}.id', alias)} or "
        f"({run}.parent_run_id is not null and {alias}.run_id = {run}.id))"
    )


def spend_columns(run: str) -> str:
    """A run's charged and reserved figures, two select-list columns named `charged_micro_usd` and
    `reserved_micro_usd` that add up to what admission counts for the same rows."""
    rows = f"from app_private.model_invocations i where {shown_for(run)}"
    return (
        f"(select coalesce(sum({charge('i')}) filter (where not ({cost_open('i')})), 0)::bigint "
        f"{rows}) as charged_micro_usd, "
        f"(select coalesce(sum({reservation('i')}) filter (where {cost_open('i')}), 0)::bigint "
        f"{rows}) as reserved_micro_usd"
    )


def unreported_column(run: str) -> str:
    """Whether a call the run's figures show worked with no charge reported, so its amount is
    still open."""
    return (
        f"exists (select 1 from app_private.model_invocations i where {shown_for(run)} "
        f"and i.status = '{InvocationStatus.UNCERTAIN.value}' and i.reconciled_at is null "
        f"and i.failure_class = '{SettlementReason.CHARGE_NOT_REPORTED.value}')"
    )


@dataclass(frozen=True)
class LedgerUsage:
    """What the ledger holds against one workspace and one root, as admission counts it."""

    active: int
    workspace_micro_usd: int
    root_micro_usd: int


# Admission's count: slots in use, the workspace's spend on the day and the root's spend.
_USAGE = (
    "select "
    "count(*) filter (where status = any(%(active)s)) as active, "
    f"coalesce(sum({spend()}) filter (where spend_day = %(day)s), 0) as workspace_micro_usd, "
    f"coalesce(sum({spend()}) filter (where {under_root('%(root)s')}), 0) as root_micro_usd "
    "from app_private.model_invocations where workspace_id = %(workspace)s"
)


async def ledger_usage(
    connection: SqlConnection, workspace_id: UUID, root_run_id: UUID, day: date
) -> LedgerUsage:
    """Read in admission's transaction, under its workspace lock, or on its own by a check."""
    row = await required_row(
        connection,
        LedgerUsageRow,
        _USAGE,
        {
            "active": _values(ACTIVE),
            **LEDGER_PARAMS,
            "day": day,
            "root": root_run_id,
            "workspace": workspace_id,
        },
    )
    return LedgerUsage(int(row.active), int(row.workspace_micro_usd), int(row.root_micro_usd))


class ModelAdmission:
    """Takes an open async connection with the restricted runtime role, in autocommit."""

    def __init__(self, connection: SqlConnection) -> None:
        self._connection = connection

    async def admit(self, request: AdmissionRequest, *, at: datetime | None = None) -> Ticket:
        """Reserve atomically. Callers for one workspace serialize on an advisory lock."""
        moment = (at or datetime.now(UTC)).astimezone(UTC)
        day = moment.date()
        async with self._connection.transaction():
            await self._connection.execute(
                "select pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (str(request.workspace_id),),
            )
            await self._connection.execute(
                "insert into app_private.model_spend_limits (workspace_id) values (%s) "
                "on conflict (workspace_id) do nothing",
                (request.workspace_id,),
            )
            limits = await required_row(
                self._connection,
                SpendLimitsRow,
                "select run_limit_micro_usd, daily_limit_micro_usd, slots "
                "from app_private.model_spend_limits where workspace_id = %s",
                (request.workspace_id,),
            )
            usage = await ledger_usage(
                self._connection, request.workspace_id, request.root_run_id, day
            )
            active, workspace_used, run_used = (
                usage.active,
                usage.workspace_micro_usd,
                usage.root_micro_usd,
            )
            cursor = await self._connection.execute(
                "select limit_micro_usd from public.runs where id = %s", (request.root_run_id,)
            )
            run_row = await cursor.fetchone()
            run_limit = (
                min(limits.run_limit_micro_usd, run_row[0])
                if run_row
                else limits.run_limit_micro_usd
            )
            if active >= limits.slots:
                raise NoInferenceSlot("both inference slots are in use")
            cost = request.worst_case_micro_usd
            run_after, workspace_after = run_used + cost, workspace_used + cost
            if run_after > run_limit or workspace_after > limits.daily_limit_micro_usd:
                raise BudgetExceeded("this would exceed the spending limit")
            invocation_id = uuid4()
            await self._connection.execute(
                "insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, "
                "role, profile, wire_id, attempt, credential_version, spend_day, "
                "reserved_micro_usd, status) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    invocation_id,
                    request.workspace_id,
                    request.root_run_id,
                    request.run_id,
                    request.role,
                    request.profile,
                    request.wire_id,
                    request.attempt,
                    request.credential_version,
                    day,
                    cost,
                    InvocationStatus.RESERVED.value,
                ),
            )
        run_percent = _percent(run_after, run_limit)
        workspace_percent = _percent(workspace_after, limits.daily_limit_micro_usd)
        return Ticket(
            invocation_id,
            cost,
            max(run_percent, workspace_percent) >= WARNING_PERCENT,
            run_percent,
            workspace_percent,
        )

    async def _transition(self, invocation_id: UUID, sets: str, *values: object) -> None:
        """Settles an active attempt. `sets` is one of this class's own assignments, never input."""
        cursor = await self._connection.execute(
            f"update app_private.model_invocations set {sets}, finished_at = now() "
            "where id = %s and status = any(%s) returning id",
            (*values, invocation_id, _values(ACTIVE)),
        )
        if await cursor.fetchone() is None:
            raise AttemptAlreadySettled("this attempt has already been settled")

    async def mark_dispatched(self, invocation_id: UUID) -> None:
        """Raises AttemptAlreadySettled if recovery closed this reservation meanwhile, so nothing is
        sent."""
        cursor = await self._connection.execute(
            "update app_private.model_invocations set status = %s "
            "where id = %s and status = %s returning id",
            (InvocationStatus.DISPATCHED.value, invocation_id, InvocationStatus.RESERVED.value),
        )
        if await cursor.fetchone() is None:
            raise AttemptAlreadySettled("this attempt was closed before it was sent")

    async def record_credential(self, invocation_id: UUID, version: int) -> None:
        """MP-06's audit. The reference is known only once the attempt has resolved its key."""
        await self._connection.execute(
            "update app_private.model_invocations set credential_version = %s where id = %s",
            (version, invocation_id),
        )

    async def record_reply(self, invocation_id: UUID, facts: ReplyFacts) -> None:
        """What the reply said about itself. It settles nothing, and holds no message content."""
        await self._connection.execute(
            "update app_private.model_invocations set finish_reason = %s, input_tokens = %s, "
            "output_tokens = %s, reasoning_tokens = %s, tool_names = %s, invalid_tool_calls = %s "
            "where id = %s",
            (
                facts.finish_reason,
                facts.input_tokens,
                facts.output_tokens,
                facts.reasoning_tokens,
                list(facts.tool_names),
                facts.invalid_tool_calls,
                invocation_id,
            ),
        )

    async def settle(
        self, invocation_id: UUID, charged_micro_usd: int, *, upstream_provider: str | None = None
    ) -> None:
        """A reported charge replaces the estimate. Estimates and charges stay separate columns."""
        await self._transition(
            invocation_id,
            "status = %s, charged_micro_usd = %s, upstream_provider = %s",
            InvocationStatus.SUCCEEDED.value,
            charged_micro_usd,
            upstream_provider or "unknown",
        )

    async def fail_before_acceptance(self, invocation_id: UUID, failure_class: str) -> None:
        """Only here is the reservation released: the provider is known not to have taken it."""
        await self._transition(
            invocation_id,
            "status = %s, failure_class = %s, charged_micro_usd = 0",
            InvocationStatus.FAILED_BEFORE_ACCEPTANCE.value,
            failure_class,
        )

    async def mark_uncertain(
        self, invocation_id: UUID, failure_class: str, accumulated_output: str = ""
    ) -> None:
        """Keeps the attempt and its reservation. It frees the slot, not the money."""
        await self._transition(
            invocation_id,
            "status = %s, failure_class = %s, accumulated_output = %s",
            InvocationStatus.UNCERTAIN.value,
            failure_class,
            accumulated_output,
        )

    async def cancel(self, invocation_id: UUID) -> str:
        """Nothing dispatched means nothing owed. Once dispatched, the outcome is unknown."""
        row = await (
            await self._connection.execute(
                "select status from app_private.model_invocations where id = %s", (invocation_id,)
            )
        ).fetchone()
        if row is None or row[0] not in ACTIVE:
            return row[0] if row else "unknown"
        if row[0] == InvocationStatus.RESERVED:
            await self._transition(
                invocation_id,
                "status = %s, charged_micro_usd = 0, failure_class = %s",
                InvocationStatus.CANCELLED.value,
                SettlementReason.CANCELLED.value,
            )
            return InvocationStatus.CANCELLED.value
        await self.mark_uncertain(invocation_id, SettlementReason.CANCELLED_AFTER_DISPATCH.value)
        return InvocationStatus.UNCERTAIN.value

    async def close_interrupted(self, run_id: UUID) -> None:
        """A dead owner's calls in `run_id`: one never sent costs nothing, and one sent may have
        happened, so its cost stays open. A closed stream or a lost process doesn't prove a provider
        stopped (SP-012, MP-08)."""
        for status, following, charged in (
            (InvocationStatus.RESERVED, InvocationStatus.CANCELLED, "charged_micro_usd = 0, "),
            (InvocationStatus.DISPATCHED, InvocationStatus.UNCERTAIN, ""),
        ):
            await self._connection.execute(
                f"update app_private.model_invocations set status = %s, {charged}"
                "failure_class = %s, finished_at = now() where run_id = %s and status = %s",
                (following.value, SettlementReason.WORKER_LOST.value, run_id, status.value),
            )

    async def reconcile(
        self, invocation_id: UUID, charged_micro_usd: int, source: str = "owner"
    ) -> None:
        """Resolve an uncertain attempt from a reported charge. A charge is never invented."""
        cursor = await self._connection.execute(
            "update app_private.model_invocations set "
            "charged_micro_usd = %s, status = %s, "
            "reconciled_at = now(), charge_source = %s "
            "where id = %s and status = %s returning id",
            (
                charged_micro_usd,
                InvocationStatus.SUCCEEDED.value,
                source,
                invocation_id,
                InvocationStatus.UNCERTAIN.value,
            ),
        )
        if await cursor.fetchone() is None:
            raise AttemptAlreadySettled("this attempt is not awaiting reconciliation")


async def remaining_daily_micro_usd(
    connection: SqlConnection, workspace_id: UUID, *, at: datetime | None = None
) -> int:
    """What's left of the workspace's UTC-day cap, counted as `admit` counts it: outstanding
    reservations plus reported charges. Reading it reserves nothing."""
    day = (at or datetime.now(UTC)).astimezone(UTC).date()
    cursor = await connection.execute(
        "select daily_limit_micro_usd from app_private.model_spend_limits where workspace_id = %s",
        (workspace_id,),
    )
    row = await cursor.fetchone()
    limit = int(row[0]) if row else DEFAULT_DAILY_LIMIT_MICRO_USD
    cursor = await connection.execute(
        f"select coalesce(sum({spend()}), 0) from app_private.model_invocations "
        "where workspace_id = %(workspace)s and spend_day = %(day)s",
        {**LEDGER_PARAMS, "workspace": workspace_id, "day": day},
    )
    used = await cursor.fetchone()
    return limit - int(used[0] if used else 0)
