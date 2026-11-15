"""The one writer of a tool attempt's receipt (SP-012, PTOL-03, Decision 0029 F8).

Each function makes one command's moves from `domain/effects.py`, and its statement admits only the
statuses those moves start from, so a receipt never moves outside the table. Callers own the
transaction: the gateway holds the lease around `start` and `reopen`, and reconciliation locks the
row before `rule`.
"""

import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from autobots.domain.effects import ReceiptCommand, ReceiptStatus, receipt_sources


class Rows(Protocol):
    # A row's columns are whatever its statement returns, so they stay untyped here.
    async def fetchone(self) -> tuple[Any, ...] | None: ...


class Connection(Protocol):
    """The worker's or the API's psycopg connection, as far as these writes use it."""

    async def execute(self, query: str, params: tuple[object, ...], /) -> Rows: ...


@dataclass(frozen=True)
class Attempt:
    """The receipt an effect's attempt commits before the effect runs."""

    operation_id: str
    run_id: UUID
    workspace_id: UUID
    tool_id: str
    tool_version: int
    argument_hash: str
    generation: int
    can_readback: bool


@dataclass(frozen=True)
class Outcome:
    """What an attempt learned. `failure_detail` is a category the tool or gateway chose, never
    text from the destination or the model."""

    status: ReceiptStatus
    result: dict[str, Any] | None = None
    failure_code: str | None = None
    failure_detail: str | None = None


@dataclass(frozen=True)
class Ruling:
    """A person's report of what the destination's own records show, kept as evidence."""

    status: ReceiptStatus
    evidence: str
    actor_id: UUID


async def start(connection: Connection, attempt: Attempt) -> bool:
    """No receipt to started. False when the operation already has one, which then answers."""
    cursor = await connection.execute(
        "insert into app_private.tool_receipts (operation_id, run_id, workspace_id, "
        "tool_id, tool_version, argument_hash, status, generation, can_readback) "
        "values (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "on conflict (operation_id) do nothing returning operation_id",
        (
            attempt.operation_id,
            attempt.run_id,
            attempt.workspace_id,
            attempt.tool_id,
            attempt.tool_version,
            attempt.argument_hash,
            ReceiptStatus.STARTED.value,
            attempt.generation,
            attempt.can_readback,
        ),
    )
    return await cursor.fetchone() is not None


async def reopen(connection: Connection, operation_id: str, generation: int) -> bool:
    """Started again for a new attempt at `generation`. A ruling covered the last attempt: its
    evidence stays, but this one is open. False when a success landed since the caller's read."""
    cursor = await connection.execute(
        "update app_private.tool_receipts set status = %s, result = null, "
        "failure_code = null, failure_detail = null, generation = %s, "
        "reconciled_at = null, updated_at = now() "
        "where operation_id = %s and status = any(%s) returning operation_id",
        (
            ReceiptStatus.STARTED.value,
            generation,
            operation_id,
            receipt_sources(ReceiptCommand.REOPEN, ReceiptStatus.STARTED),
        ),
    )
    return await cursor.fetchone() is not None


async def record(
    connection: Connection, operation_id: str, outcome: Outcome, generation: int
) -> None:
    """Only moves a receipt forward. A success is recorded whoever owns the run now, as the effect
    happened, even over a ruling that it hadn't: repeating it would be the worse mistake, and the
    ruling's evidence stays. Anything else speaks only for the attempt on record, at `generation`
    or an earlier one."""
    sources = receipt_sources(ReceiptCommand.RECORD, outcome.status)
    values = (
        outcome.status.value,
        json.dumps(outcome.result) if outcome.result is not None else None,
        outcome.failure_code,
        outcome.failure_detail,
        operation_id,
        sources,
    )
    if outcome.status is ReceiptStatus.SUCCEEDED:
        await connection.execute(
            "update app_private.tool_receipts set status = %s, result = %s, failure_code = %s, "
            "failure_detail = %s, updated_at = now() "
            "where operation_id = %s and status = any(%s)",
            values,
        )
        return
    await connection.execute(
        "update app_private.tool_receipts set status = %s, result = %s, failure_code = %s, "
        "failure_detail = %s, updated_at = now() "
        "where operation_id = %s and status = any(%s) and generation <= %s",
        (*values, generation),
    )


async def mark_unknown(connection: Connection, run_id: UUID, generation: int) -> None:
    """A dead owner's started attempts, from generations before `generation`, may have happened."""
    await connection.execute(
        "update app_private.tool_receipts set status = %s, updated_at = now() "
        "where run_id = %s and status = any(%s) and generation < %s",
        (
            ReceiptStatus.UNKNOWN.value,
            run_id,
            receipt_sources(ReceiptCommand.MARK_UNKNOWN, ReceiptStatus.UNKNOWN),
            generation,
        ),
    )


async def rule(connection: Connection, operation_id: str, ruling: Ruling) -> None:
    """An unknown outcome settled by a person's ruling. Delivered closes it with no retry, and not
    delivered allows one fresh attempt (SP-012)."""
    result = {"reconciled": "operator"} if ruling.status is ReceiptStatus.SUCCEEDED else None
    await connection.execute(
        "update app_private.tool_receipts set status = %s, result = %s, evidence = %s, "
        "reconciled_by = %s, reconciled_at = now(), updated_at = now() "
        "where operation_id = %s and status = any(%s)",
        (
            ruling.status.value,
            json.dumps(result) if result else None,
            ruling.evidence,
            ruling.actor_id,
            operation_id,
            receipt_sources(ReceiptCommand.RULE, ruling.status),
        ),
    )


async def settle_for_review(connection: Connection, operation_id: str, run_id: UUID) -> None:
    """The attempt's receipt counts as ruled, with its status unchanged, so the approval gate
    doesn't count it as having used the decision a person makes next (Decision 0022 D15)."""
    await connection.execute(
        "update app_private.tool_receipts set reconciled_at = now() "
        "where operation_id = %s and run_id = %s",
        (operation_id, run_id),
    )
