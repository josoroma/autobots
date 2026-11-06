"""Slots and spend, MP-07. Admission happens under a workspace lock, before any provider call."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

# What still holds a slot. A settled or uncertain attempt no longer does.
ACTIVE = ("reserved", "dispatched")
# What still counts against a budget, in full, because its cost isn't settled.
OUTSTANDING = ("reserved", "dispatched", "uncertain")
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


class ModelAdmission:
    """Takes an open async connection with the restricted runtime role, in autocommit."""

    def __init__(self, connection: Any) -> None:
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
            limits = await (
                await self._connection.execute(
                    "select run_limit_micro_usd, daily_limit_micro_usd, slots "
                    "from app_private.model_spend_limits where workspace_id = %s",
                    (request.workspace_id,),
                )
            ).fetchone()
            usage = await (
                await self._connection.execute(
                    "select "
                    "count(*) filter (where status = any(%(active)s)), "
                    "coalesce(sum(case when status = any(%(outstanding)s) then reserved_micro_usd "
                    "else coalesce(charged_micro_usd, 0) end) "
                    "filter (where spend_day = %(day)s), 0), "
                    "coalesce(sum(case when status = any(%(outstanding)s) then reserved_micro_usd "
                    "else coalesce(charged_micro_usd, 0) end) "
                    "filter (where root_run_id = %(root)s), 0) "
                    "from app_private.model_invocations where workspace_id = %(workspace)s",
                    {
                        "active": list(ACTIVE),
                        "outstanding": list(OUTSTANDING),
                        "day": day,
                        "root": request.root_run_id,
                        "workspace": request.workspace_id,
                    },
                )
            ).fetchone()
            active, workspace_used, run_used = usage
            cursor = await self._connection.execute(
                "select limit_micro_usd from public.runs where id = %s", (request.root_run_id,)
            )
            run_row = await cursor.fetchone()
            run_limit = min(limits[0], run_row[0]) if run_row else limits[0]
            if active >= limits[2]:
                raise NoInferenceSlot("both inference slots are in use")
            cost = request.worst_case_micro_usd
            run_after, workspace_after = run_used + cost, workspace_used + cost
            if run_after > run_limit or workspace_after > limits[1]:
                raise BudgetExceeded("this would exceed the spending limit")
            invocation_id = uuid4()
            await self._connection.execute(
                "insert into app_private.model_invocations (id, workspace_id, root_run_id, run_id, "
                "role, profile, wire_id, attempt, credential_version, spend_day, "
                "reserved_micro_usd, status) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'reserved')",
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
                ),
            )
        run_percent = _percent(run_after, run_limit)
        workspace_percent = _percent(workspace_after, limits[1])
        return Ticket(
            invocation_id,
            cost,
            max(run_percent, workspace_percent) >= WARNING_PERCENT,
            run_percent,
            workspace_percent,
        )

    async def _transition(self, invocation_id: UUID, sets: str, *values: Any) -> None:
        cursor = await self._connection.execute(
            f"update app_private.model_invocations set {sets}, finished_at = now() "
            "where id = %s and status in ('reserved', 'dispatched') returning id",
            (*values, invocation_id),
        )
        if await cursor.fetchone() is None:
            raise ValueError("this attempt has already been settled")

    async def mark_dispatched(self, invocation_id: UUID) -> None:
        """Raises if recovery closed this reservation meanwhile, so nothing is sent."""
        cursor = await self._connection.execute(
            "update app_private.model_invocations set status = 'dispatched' "
            "where id = %s and status = 'reserved' returning id",
            (invocation_id,),
        )
        if await cursor.fetchone() is None:
            raise ValueError("this attempt was closed before it was sent")

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
            "status = 'succeeded', charged_micro_usd = %s, upstream_provider = %s",
            charged_micro_usd,
            upstream_provider or "unknown",
        )

    async def fail_before_acceptance(self, invocation_id: UUID, failure_class: str) -> None:
        """Only here is the reservation released: the provider is known not to have taken it."""
        await self._transition(
            invocation_id,
            "status = 'failed_before_acceptance', failure_class = %s, charged_micro_usd = 0",
            failure_class,
        )

    async def mark_uncertain(
        self, invocation_id: UUID, failure_class: str, accumulated_output: str = ""
    ) -> None:
        """Keeps the attempt and its reservation. It frees the slot, not the money."""
        await self._transition(
            invocation_id,
            "status = 'uncertain', failure_class = %s, accumulated_output = %s",
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
        if row[0] == "reserved":
            await self._transition(
                invocation_id,
                "status = 'cancelled', charged_micro_usd = 0, failure_class = %s",
                "cancelled",
            )
            return "cancelled"
        await self.mark_uncertain(invocation_id, "cancelled_after_dispatch")
        return "uncertain"

    async def reconcile(
        self, invocation_id: UUID, charged_micro_usd: int, source: str = "owner"
    ) -> None:
        """Resolve an uncertain attempt from a reported charge. A charge is never invented."""
        cursor = await self._connection.execute(
            "update app_private.model_invocations set "
            "charged_micro_usd = %s, status = 'succeeded', "
            "reconciled_at = now(), charge_source = %s "
            "where id = %s and status = 'uncertain' returning id",
            (charged_micro_usd, source, invocation_id),
        )
        if await cursor.fetchone() is None:
            raise ValueError("this attempt is not awaiting reconciliation")
