"""The one place a tool runs. Every check happens before the effect, SP-013 and PRD 9.1.

What a tool is, is handed and returns is in tool_definitions.py (PTOL-07)."""

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from autobots.application import receipts, tool_switches
from autobots.application.approvals import (
    ApprovalProposal,
    ApprovedRequest,
    approval_gate,
    approved_request,
    receipt_may_have_sent,
    scope_snapshot,
)
from autobots.application.runs import LeaseLost
from autobots.application.sql import SqlConnection, one, optional_row
from autobots.application.tool_definitions import (
    APPROVAL_POLICY_VERSION,
    NotDelivered,
    OutcomeUnknown,
    ToolContext,
    ToolDefinition,
    ToolFailed,
    ToolRegistry,
    ToolResult,
    ToolScope,
)

# The gateway's own fenced writes use it, and so do the writers that import it from this module.
from autobots.application.worker_leases import hold_lease as hold_lease
from autobots.domain.effects import ReceiptStatus, leaves_receipt
from autobots.domain.runs import RunStatus
from autobots.domain.stops import GatewayCode
from autobots.domain.tools import OperationClass, ToolOutcome, path_granted
from autobots.logs import log_event
from autobots.persistence.rows import OwnershipRow

logger = logging.getLogger("autobots.tools")


# Codes the gateway alone records on a receipt; a tool raising one is recorded as tool_failed.
GATEWAY_ONLY = frozenset({GatewayCode.LEASE_LOST, GatewayCode.RUN_NOT_RUNNING})


def _hash(arguments: BaseModel) -> str:
    encoded = json.dumps(arguments.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _identity(scope: ToolScope, tool: ToolDefinition, argument_hash: str) -> str:
    # Two foreach items can be equal and still be two pieces of work.
    place = f"|{scope.instance}" if scope.instance else ""
    identity = f"{scope.run_id}{place}|{tool.tool_id}|{tool.version}|{argument_hash}"
    return hashlib.sha256(identity.encode()).hexdigest()


def _operation_id(scope: ToolScope, tool: ToolDefinition, parsed: BaseModel) -> str:
    """The same identity `resolve` gives a call, from its parsed arguments."""
    return _identity(scope, tool, _hash(parsed))


@dataclass(frozen=True)
class Call:
    """One tool call, resolved once per dispatch: its granted definition, its parsed arguments,
    and the identity that binds an approval to its effect and names its receipt (SP-013)."""

    tool: ToolDefinition
    parsed: BaseModel
    argument_hash: str
    operation_id: str


@dataclass(frozen=True)
class Refused:
    """Why `resolve` refused a call, with the definition and parsed arguments it reached first,
    which the call's tool-use record shows (TU-01, TU-04)."""

    code: GatewayCode
    tool: ToolDefinition | None = None
    parsed: BaseModel | None = None


def resolve(
    registry: ToolRegistry, scope: ToolScope, name: str, arguments: object
) -> Call | Refused:
    """The call, or why it is refused before anything about the run is read: not granted, not
    registered, an executor no longer qualified, invalid arguments or a path outside the grants,
    in that order (SP-013)."""
    version = scope.tools.get(name)
    if version is None:
        return Refused(GatewayCode.TOOL_NOT_GRANTED)
    tool = registry.get(name, version)
    if tool is None:
        return Refused(GatewayCode.TOOL_NOT_REGISTERED)
    parsed: BaseModel | None
    try:
        # Parsed before the qualification check so that refusal's record still shows the call's
        # public fields; the refusals keep their order.
        parsed = tool.input_model.model_validate(arguments)
    except ValidationError:
        parsed = None
    if tool.operation_class is OperationClass.ARBITRARY_EXECUTION and not tool.executor_qualified():
        # Checked at each call, as a qualification can be withdrawn while a worker runs (AB-02).
        return Refused(GatewayCode.CAPABILITY_DISABLED, tool, parsed)
    if parsed is None:
        return Refused(GatewayCode.INVALID_ARGUMENTS, tool)
    if not all(path_granted(path, scope.paths) for path in tool.resources(parsed)):
        return Refused(GatewayCode.RESOURCE_NOT_GRANTED, tool, parsed)
    argument_hash = _hash(parsed)
    return Call(tool, parsed, argument_hash, _identity(scope, tool, argument_hash))


async def _target_unchanged(
    connection: SqlConnection,
    operation_id: str,
    approval: ApprovedRequest | None,
    target: str | None,
) -> bool:
    """Decision 0025 V7 and V8: an approved effect runs only against the target it was approved
    for, and an empty recorded target fails closed. One already sent, or possibly sent, is left to
    its receipt and reconciliation, as refusing it would report an effect that happened as not."""
    cursor = await connection.execute(
        "select status from app_private.tool_receipts where operation_id = %s", (operation_id,)
    )
    receipt = await cursor.fetchone()
    if receipt_may_have_sent(None if receipt is None else receipt[0]):
        return True
    recorded = approval.resource_target if approval is not None else None
    return bool(recorded) and recorded == target


async def _has_approval(connection: SqlConnection, operation_id: str) -> bool:
    cursor = await connection.execute(
        "select 1 from public.approval_requests where operation_id = %s", (operation_id,)
    )
    return await cursor.fetchone() is not None


def _denied(code: GatewayCode | str) -> ToolResult:
    return ToolResult(ToolOutcome.DENIED, code)


def _diagnosis(error: BaseException) -> str:
    """Why an effect's outcome is unknown, for its receipt: the tool's own category, the gateway's
    timeout, or the type of a defect. Never the message, which can hold a reply or a key."""
    if isinstance(error, OutcomeUnknown):
        return error.detail
    if isinstance(error, TimeoutError):
        return "timeout"
    kind = type(error)
    return f"defect:{kind.__module__}.{kind.__qualname__}"


def _log_failure(
    event: str, tool: ToolDefinition, operation_id: str | None, error: BaseException
) -> None:
    """One private line for a failure the tool didn't choose, in PRD-LangChain-Deep-Agents 12.2's
    `tool.operation.*`. A defect needs someone to look; a timeout or unclear reply is degraded."""
    fields: dict[str, object] = {"tool": tool.tool_id, "version": tool.version, "error": error}
    if operation_id is not None:
        fields["operation"] = operation_id
    level = logging.ERROR if _diagnosis(error).startswith("defect:") else logging.WARNING
    log_event(logger, event, level, **fields)


async def _expert_behind(connection: SqlConnection, scope: ToolScope) -> bool:
    """The run was admitted from an Expert's binding, the only place such a grant comes from."""
    cursor = await connection.execute(
        "select expert_id is not null from public.runs where id = %s and workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    row = await cursor.fetchone()
    return bool(row and row[0])


async def ownership_refusal(connection: SqlConnection, scope: ToolScope) -> GatewayCode | None:
    """Run status and ownership, read fresh by database time."""
    row = await optional_row(
        connection,
        OwnershipRow,
        "select r.status as run_status, j.status as job_status, j.generation, "
        "j.lease_expires_at > clock_timestamp() as lease_live "
        "from public.runs r join app_private.run_jobs j on j.run_id = r.id "
        "where r.id = %s and r.workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    if row is None:
        return GatewayCode.RUN_NOT_FOUND
    if row.job_status != "claimed" or row.generation != scope.generation or not row.lease_live:
        return GatewayCode.LEASE_LOST
    if row.run_status != RunStatus.RUNNING.value:
        return GatewayCode.RUN_NOT_RUNNING
    return None


class NotRunning(Exception):
    """The run stopped after this worker last looked, so nothing is admitted."""


async def hold_running(connection: SqlConnection, scope: ToolScope) -> None:
    """Inside the admission's transaction, so a cancel can't land between this and the receipt."""
    await hold_lease(connection, scope)
    cursor = await connection.execute(
        "select status from public.runs where id = %s for share", (scope.run_id,)
    )
    row = await cursor.fetchone()
    if row is None or row[0] != RunStatus.RUNNING.value:
        raise NotRunning


async def admission_refusal(
    connection: SqlConnection, scope: ToolScope, call: Call
) -> GatewayCode | None:
    """The run is running and this worker owns it, the tool and its group are on for the
    workspace (Decision 0033 W2), and an Expert-only tool has an Expert behind the run (AB-02).
    Each is read fresh, after the call resolved and before any approval or metering."""
    refusal = await ownership_refusal(connection, scope)
    if refusal is not None:
        return refusal
    tool = call.tool
    if await tool_switches.turned_off(
        connection, scope.workspace_id, tool.tool_id, tool.group.value
    ):
        return GatewayCode.TOOL_TURNED_OFF
    if tool.expert_only and not await _expert_behind(connection, scope):
        return GatewayCode.EXPERT_GRANT_REQUIRED
    return None


def _proposal(
    scope: ToolScope, call: Call, target: str | None, detail: dict[str, Any] | None
) -> ApprovalProposal:
    tool, policy = call.tool, call.tool.approval
    return ApprovalProposal(
        operation_id=call.operation_id,
        tool_id=tool.tool_id,
        tool_version=tool.version,
        operation_class=tool.operation_class.value,
        argument_hash=call.argument_hash,
        arguments=tool.redact(call.parsed.model_dump(mode="json")),
        scope=scope_snapshot(scope.tools, scope.paths),
        policy_version=APPROVAL_POLICY_VERSION,
        policy_rule=policy.rule(tool.operation_class),
        policy_reason=policy.reason_text(tool.operation_class),
        resource_target=target,
        review_detail=detail,
    )


@dataclass(frozen=True)
class Released:
    """A call the approval step lets through, with what a person approved for it, or None when no
    policy held it (XMOD-02)."""

    approval: ApprovedRequest | None = None


async def hold_for_approval(
    connection: SqlConnection, scope: ToolScope, call: Call
) -> GatewayCode | str | Released:
    """Released lets the call through: its policy doesn't hold it, or a person approved this
    operation and its target still resolves to the one they approved (Decision 0015, Decision 0025
    V7). The approved request is read once here, for the tool's context.

    A code means it waits for a person or is refused. A tool's own code from its target resolver
    or review passes through."""
    tool, policy = call.tool, call.tool.approval
    if not policy.applies(tool.operation_class, call.parsed):
        return Released()
    reviewing = ToolContext(connection, scope, call.operation_id)
    target = policy.resource_target(call.parsed)
    if policy.target_resolver is not None:
        try:
            target = await policy.target_resolver(call.parsed, reviewing)
        except ToolFailed as error:
            # Nothing to approve: the destination isn't configured for this workspace.
            return str(error) or GatewayCode.CONNECTOR_NOT_CONFIGURED
    detail = None
    if policy.review_detail is not None and not await _has_approval(connection, call.operation_id):
        try:
            detail = await asyncio.wait_for(
                policy.review_detail(call.parsed, reviewing), tool.timeout_seconds
            )
        except ToolFailed as error:
            return str(error) or GatewayCode.REVIEW_UNAVAILABLE
        except Exception as error:  # noqa: BLE001 - a review that can't be built denies the call, so nothing runs
            # A denial keeps no receipt, so the log line is all that's kept.
            _log_failure("tool.operation.review_failed", tool, call.operation_id, error)
            return GatewayCode.REVIEW_UNAVAILABLE
    code = await approval_gate(connection, scope, _proposal(scope, call, target, detail))
    if code is not None:
        return code
    approved = await approved_request(connection, call.operation_id)
    if policy.target_resolver is not None and not await _target_unchanged(
        connection, call.operation_id, approved, target
    ):
        return GatewayCode.APPROVAL_TARGET_CHANGED
    return Released(approved)


async def admit_budget(
    connection: SqlConnection, scope: ToolScope, call: Call, use: int | None
) -> GatewayCode | None:
    """Decision 0017 Q4: a metered call is counted per root run tree, before any request leaves.
    After approval, so a call waiting for a person isn't counted twice."""
    from autobots.application.tool_uses import admit_metered, is_metered

    if not is_metered(call.tool):
        return None
    if use is None or not await admit_metered(connection, scope, use):
        return GatewayCode.TOOL_BUDGET_EXCEEDED
    return None


@dataclass(frozen=True)
class ToolGateway:
    registry: ToolRegistry

    async def execute(
        self, connection: SqlConnection, scope: ToolScope, name: str, arguments: object
    ) -> ToolResult:
        """Every dispatch is recorded, denials included, before and after it runs (TU-01). A worker
        that lost its lease records nothing, and is refused below as before."""
        from autobots.application.tool_uses import begin_use, complete_use

        resolved = resolve(self.registry, scope, name, arguments)
        use = await begin_use(connection, scope, name, arguments, resolved)
        result = await self._dispatch(connection, scope, resolved, use)
        if use is not None:
            # A call now waiting for a person released the lease in its own approval gate.
            waiting = result.code == GatewayCode.APPROVAL_PENDING
            await complete_use(connection, scope, use, name, resolved, result, fenced=not waiting)
        return result

    async def _dispatch(
        self, connection: SqlConnection, scope: ToolScope, resolved: Call | Refused, use: int | None
    ) -> ToolResult:
        """Refused before any effect, in the order that is the gateway's security contract (SP-013):
        the call doesn't resolve, admission refuses it, it waits for a person or is refused at
        approval, or the metered budget refuses it."""
        if isinstance(resolved, Refused):
            return _denied(resolved.code)
        call = resolved
        approval = None
        refusal: GatewayCode | str | None = await admission_refusal(connection, scope, call)
        if refusal is None:
            held = await hold_for_approval(connection, scope, call)
            if isinstance(held, Released):
                approval = held.approval
            else:
                refusal = held
        if refusal is None:
            refusal = await admit_budget(connection, scope, call, use)
        if refusal is not None:
            return _denied(refusal)
        if leaves_receipt(call.tool.operation_class):
            return await self.admit_effect(connection, scope, call, approval)
        return await self._read(connection, scope, call, approval)

    async def _read(
        self,
        connection: SqlConnection,
        scope: ToolScope,
        call: Call,
        approval: ApprovedRequest | None,
    ) -> ToolResult:
        """No effect, so no receipt. A repeated read must see current content. One a person
        approved has used that approval up (PTOL-06)."""
        tool = call.tool
        context = ToolContext(connection, scope, None, approval)
        for attempt in range(tool.retries + 1):
            try:
                output = await asyncio.wait_for(
                    tool.handler(call.parsed, context), tool.timeout_seconds
                )
                # An output its model refuses is a defect in the read, recorded like any other.
                visible, too_large = _visible(tool, output)
            except TimeoutError:
                code = GatewayCode.TOOL_TIMEOUT
            except ToolFailed as error:
                return ToolResult(ToolOutcome.FAILED, str(error) or GatewayCode.TOOL_FAILED)
            except Exception as error:  # noqa: BLE001 - any tool failure is recorded as tool_failed
                # A read keeps no receipt, so the log line is all that's kept.
                _log_failure("tool.operation.failed", tool, None, error)
                code = GatewayCode.TOOL_FAILED
            else:
                if too_large:
                    return ToolResult(ToolOutcome.FAILED, GatewayCode.OUTPUT_TOO_LARGE)
                return ToolResult(ToolOutcome.SUCCEEDED, output=visible)
            if attempt < tool.retries:
                refusal = await ownership_refusal(connection, scope)
                if refusal is not None:
                    return _denied(refusal)
        return ToolResult(ToolOutcome.FAILED, code)

    async def admit_effect(
        self,
        connection: SqlConnection,
        scope: ToolScope,
        call: Call,
        approval: ApprovedRequest | None = None,
    ) -> ToolResult:
        """The effect step `_dispatch` takes once every check passed, with what a person approved
        for it. The receipt commits as started, under the lease, before the effect runs, so a
        worker that stalled after its checks admits nothing (SP-012, SP-013). A database check
        drives it as that stalled worker; everything else calls `execute`."""
        operation_id = call.operation_id
        context = ToolContext(connection, scope, operation_id, approval)
        attempt = receipts.Attempt(
            operation_id,
            scope.run_id,
            scope.workspace_id,
            call.tool.tool_id,
            call.tool.version,
            call.argument_hash,
            scope.generation,
            call.tool.reconcile is not None,
        )
        # Committed before the effect starts, so a crash leaves a record that it may have happened.
        # The lease is held for it, so a worker that stalled after its check can't admit anything.
        try:
            async with connection.transaction():
                await hold_running(connection, scope)
                created = await receipts.start(connection, attempt)
            if not created:
                replayed = await replay_receipt(context, call)
                if replayed is not None:
                    return replayed
                # A crash during this new attempt has to be classified like any other.
                async with connection.transaction():
                    await hold_running(connection, scope)
                    reopened = await receipts.reopen(connection, operation_id, scope.generation)
                if not reopened:
                    # A late success or a person's ruling landed since that read. Never send again.
                    replayed = await replay_receipt(context, call)
                    if replayed is not None:
                        return replayed
                    return _denied(GatewayCode.LEASE_LOST)
        except LeaseLost:
            return _denied(GatewayCode.LEASE_LOST)
        except NotRunning:
            return _denied(GatewayCode.RUN_NOT_RUNNING)
        return await self._attempt(context, call)

    async def _attempt(self, context: ToolContext, call: Call) -> ToolResult:
        """Runs the effect once and records on its receipt what is known about it."""
        tool = call.tool
        try:
            output = await asyncio.wait_for(
                tool.handler(call.parsed, context), tool.timeout_seconds
            )
            # The handler returned, so the effect happened: an output its model refuses is a defect
            # whose outcome is unknown, never an escape that leaves the receipt started (XERR-02).
            visible, too_large = _visible(tool, output)
        except ToolFailed as error:
            return await _known_failure(context, call, error)
        except LeaseLost:
            # The write's transaction refused it, so nothing happened. The code tells the approval
            # gate that this attempt didn't use a person's decision.
            await record_receipt(
                context, call.operation_id, ReceiptStatus.FAILED, None, GatewayCode.LEASE_LOST
            )
            return ToolResult(
                ToolOutcome.DENIED, GatewayCode.LEASE_LOST, operation_id=call.operation_id
            )
        except Exception as error:  # noqa: BLE001 - an unexpected failure leaves the outcome unknown for reconciliation
            return await _unexpected_failure(context, call, error)
        if too_large:
            await record_receipt(
                context,
                call.operation_id,
                ReceiptStatus.UNKNOWN,
                None,
                failure_detail="output_too_large",
            )
            return ToolResult(
                ToolOutcome.UNKNOWN, GatewayCode.OUTPUT_TOO_LARGE, operation_id=call.operation_id
            )
        return await _succeeded(context, call, visible)


async def replay_receipt(context: ToolContext, call: Call) -> ToolResult | None:
    """The earlier outcome, if there is one. None means it failed for certain, so try again.

    At module level, so a database check can land a late success between two of its reads by
    swapping it with `patch.object` (TDBC-02)."""
    tool, operation_id = call.tool, call.operation_id
    status, result = await one(
        context.connection,
        "select status, result from app_private.tool_receipts where operation_id = %s",
        (operation_id,),
    )
    if status == ReceiptStatus.SUCCEEDED:
        return ToolResult(
            ToolOutcome.SUCCEEDED, output=result, operation_id=operation_id, replayed=True
        )
    if status == ReceiptStatus.FAILED:
        return None
    # An earlier attempt was interrupted, and this is why its outcome stays unknown.
    detail = "interrupted"
    if tool.reconcile is not None:
        try:
            found = await asyncio.wait_for(
                tool.reconcile(call.parsed, context), tool.timeout_seconds
            )
            # A readback whose output its model refuses is a failed readback.
            visible = None if found is None else _visible(tool, found)[0]
        except NotDelivered:
            return None
        except Exception as error:  # noqa: BLE001 - a failed reconcile leaves the effect unknown, never assumed
            _log_failure("tool.operation.readback_failed", tool, operation_id, error)
            detail = f"readback:{_diagnosis(error)}"
            visible = None
        if visible is not None:
            await record_receipt(context, operation_id, ReceiptStatus.SUCCEEDED, visible)
            return ToolResult(
                ToolOutcome.SUCCEEDED, output=visible, operation_id=operation_id, replayed=True
            )
    if tool.safe_to_repeat:
        return None
    await record_receipt(context, operation_id, ReceiptStatus.UNKNOWN, None, failure_detail=detail)
    return ToolResult(
        ToolOutcome.UNKNOWN,
        GatewayCode.OUTCOME_UNKNOWN,
        operation_id=operation_id,
        replayed=True,
    )


async def _known_failure(context: ToolContext, call: Call, error: ToolFailed) -> ToolResult:
    """The tool knows the effect didn't happen, and says why with its own code and detail."""
    code = str(error) or GatewayCode.TOOL_FAILED
    detail = error.detail
    if code in GATEWAY_ONLY:
        # Only the gateway may say the lease refused an attempt: the approval gate trusts that code
        # to mean nothing was written (Decision 0025 V8).
        code, detail = GatewayCode.TOOL_FAILED, f"reserved_code:{code}"
    await record_receipt(context, call.operation_id, ReceiptStatus.FAILED, None, code, detail)
    return ToolResult(ToolOutcome.FAILED, code, operation_id=call.operation_id)


async def _unexpected_failure(context: ToolContext, call: Call, error: BaseException) -> ToolResult:
    """A failure the tool didn't choose leaves the outcome unknown, for a readback or a person to
    settle. Its receipt keeps the diagnosis and its log line the cause (R-25, XERR-02)."""
    _log_failure("tool.operation.unknown", call.tool, call.operation_id, error)
    await record_receipt(
        context, call.operation_id, ReceiptStatus.UNKNOWN, None, failure_detail=_diagnosis(error)
    )
    return ToolResult(
        ToolOutcome.UNKNOWN, GatewayCode.OUTCOME_UNKNOWN, operation_id=call.operation_id
    )


async def _succeeded(context: ToolContext, call: Call, visible: dict[str, Any]) -> ToolResult:
    # The effect happened, so it is recorded whoever owns the run now.
    await record_receipt(context, call.operation_id, ReceiptStatus.SUCCEEDED, visible)
    refusal = await ownership_refusal(context.connection, context.scope)
    if refusal is not None:
        return ToolResult(ToolOutcome.DENIED, refusal, operation_id=call.operation_id)
    return ToolResult(ToolOutcome.SUCCEEDED, output=visible, operation_id=call.operation_id)


def _visible(tool: ToolDefinition, output: BaseModel) -> tuple[dict[str, Any], bool]:
    checked = tool.output_model.model_validate(output.model_dump())
    visible = tool.redact(checked.model_dump(mode="json"))
    return visible, len(json.dumps(visible).encode()) > tool.max_output_bytes


async def record_receipt(
    context: ToolContext,
    operation_id: str,
    status: ReceiptStatus,
    result: dict[str, Any] | None,
    failure_code: str | None = None,
    failure_detail: str | None = None,
) -> None:
    """What this attempt learned, on its receipt, by receipts.record: a success whoever owns the
    run now, anything else only for the attempt on record at this context's generation. A
    database check passes the stored strings, which name the same statuses."""
    outcome = receipts.Outcome(ReceiptStatus(status), result, failure_code, failure_detail)
    await receipts.record(context.connection, operation_id, outcome, context.scope.generation)
