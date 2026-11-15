"""The one place a tool runs. Every check happens before the effect, SP-013 and PRD 9.1."""

import asyncio
import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ValidationError

from autobots.application.approvals import (
    ApprovalProposal,
    approval_gate,
    approved_request,
    receipt_may_have_sent,
    scope_snapshot,
)
from autobots.application.runs import LeaseLost

# The gateway's own fenced writes use it, and so do the writers that import it from this module.
from autobots.application.worker_leases import hold_lease as hold_lease
from autobots.domain.runs import RunStatus
from autobots.domain.stops import GatewayCode
from autobots.domain.tool_catalog import CostClass, KeyRequirement, ToolGroup, ToolProvider
from autobots.domain.tools import EFFECTFUL, OperationClass, ToolOutcome, path_granted

# Written through the standard logger, as STD-01 keeps this layer from importing
# operations/logs.py; that module's formatter renders the record and its conventions apply.
logger = logging.getLogger("autobots.tools")


class NotDelivered(Exception):
    """A readback found the effect never reached the destination, so one new attempt is safe."""


class OutcomeUnknown(Exception):
    """The tool can't tell whether its effect happened, so the outcome stays unknown for a person
    or a readback to settle.

    `detail` is a category the tool chose, such as `github_unclear_502`, never text from the
    destination or the model. It's stored on the receipt (R-25, XERR-02).
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


# Codes the gateway alone records on a receipt; a tool raising one is recorded as tool_failed.
GATEWAY_ONLY = frozenset({GatewayCode.LEASE_LOST, GatewayCode.RUN_NOT_RUNNING})


class ToolFailed(Exception):
    """The tool knows the effect did not happen. Anything else raised leaves the outcome unknown.

    `detail` is for diagnosis only: a category the tool chose, never text the model wrote. It's
    stored on the receipt and doesn't reach the model.
    """

    def __init__(self, *args: object, detail: str | None = None) -> None:
        super().__init__(*args)
        self.detail = detail


@dataclass(frozen=True)
class ToolScope:
    """Grants pin a version, and anything not listed is denied."""

    workspace_id: UUID
    run_id: UUID
    generation: int
    tools: Mapping[str, int]
    paths: tuple[str, ...] = ()
    root_run_id: UUID | None = None
    parent_run_id: UUID | None = None
    instance: str | None = None

    @property
    def budget_run_id(self) -> UUID:
        """Retries and descendants spend from the same tree, SP-008."""
        return self.root_run_id or self.run_id


@dataclass(frozen=True)
class ToolContext:
    connection: Any
    scope: ToolScope
    operation_id: str | None


Handler = Callable[[Any, ToolContext], Awaitable[BaseModel]]
Reconcile = Callable[[Any, ToolContext], Awaitable[BaseModel | None]]

# Decision 0015. Change it whenever ApprovalPolicy's condition, rule or reason text changes, so a
# request names the rules it was held under. The pin test in test_tools.py fails until it changes.
# Version 2 adds a tool's per-call condition, ApprovalPolicy's `when` (Decision 0026 C3).
APPROVAL_POLICY_VERSION = "approval-policy/2"


def _no_target(_: Any) -> str | None:
    return None


@dataclass(frozen=True)
class ApprovalPolicy:
    """When a call waits for a person, and what its request records (Decision 0015). A tool
    declares it as `ToolDefinition.approval`, and the gateway, the catalog and the pin test all
    read it, so the rule is written once (PTOL-04).

    A consequential external write always waits. Any other call waits when its tool is marked
    `always`, or when `when` holds for its parsed arguments (Decision 0026 C3).
    """

    always: bool = False
    when: Callable[[Any], bool] | None = None
    # Why policy asks, when the tool has a reason of its own. Never from the model.
    reason: str | None = None
    # What a reviewer is told this touches, from the arguments or server configuration.
    resource_target: Callable[[Any], str | None] = _no_target
    # Decision 0025 V7: the target resolved for this call's workspace. When set, it is what the
    # approval records, and an approved call whose target now resolves differently is refused.
    target_resolver: Callable[[Any, ToolContext], Awaitable[str | None]] | None = None
    # PRD-Studio GH-06: what the reviewer sees beyond the arguments, read before the approval
    # request exists. It may read the destination, never write it.
    review_detail: Callable[[Any, ToolContext], Awaitable[dict[str, Any]]] | None = None

    def _every_call(self, operation_class: OperationClass) -> bool:
        return self.always or operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE

    def applies(self, operation_class: OperationClass, parsed: Any) -> bool:
        """Whether this call, with these parsed arguments, waits for a person."""
        return self._every_call(operation_class) or (self.when is not None and self.when(parsed))

    def label(self, operation_class: OperationClass) -> Literal["always", "by_action", "never"]:
        """How the catalog shows the policy (Decision 0026 C9)."""
        if self._every_call(operation_class):
            return "always"
        return "by_action" if self.when is not None else "never"

    def rule(self, operation_class: OperationClass) -> str:
        """Which of the policy's rules held a call."""
        if operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE:
            return "consequential_external_write"
        if not self.always and self.when is not None:
            return "action_marked"
        return "tool_marked"

    def reason_text(self, operation_class: OperationClass) -> str:
        """Fixed text from the tool's policy, so nothing a model wrote can reach it."""
        if self.reason is not None:
            return self.reason
        if operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE:
            return (
                "This tool changes something outside this Mac, so policy holds each call for a "
                "person."
            )
        return "This tool is marked to wait for a person, so policy holds each call."


@dataclass(frozen=True)
class ToolDefinition:
    tool_id: str
    version: int
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    operation_class: OperationClass
    handler: Handler
    timeout_seconds: float = 10.0
    retries: int = 0
    max_output_bytes: int = 300_000
    # When a call waits for a person and what its request records. The default holds only a
    # consequential external write.
    approval: ApprovalPolicy = field(default_factory=ApprovalPolicy)
    # What the arguments touch, checked against the scope's path grants.
    resources: Callable[[Any], tuple[str, ...]] = lambda _: ()
    # Finds out whether an interrupted effect happened, from the destination rather than memory.
    reconcile: Reconcile | None = None
    # The destination refuses duplicates, so finishing an interrupted attempt can't repeat it.
    safe_to_repeat: bool = False
    # Applied to anything returned to the model or stored in a receipt.
    redact: Callable[[dict[str, Any]], dict[str, Any]] = lambda output: output
    # How the catalog describes it, PRD-Tool-Catalog TC-02. None of these grant anything.
    title: str = ""
    group: ToolGroup = ToolGroup.GENERAL
    provider: ToolProvider = ToolProvider.AUTOBOTS
    network: bool = False
    cost_class: CostClass = CostClass.FREE_LOCAL
    cost_note: str | None = None
    key_requirement: KeyRequirement | None = None
    # Top-level fields a run's screens may show, TU-04. The default shows none.
    public_input_fields: tuple[str, ...] = ()
    public_output_fields: tuple[str, ...] = ()
    # AB-02: an `arbitrary_execution` tool exists only while its executor reports qualified.
    qualified: Callable[[], bool] | None = None
    # Granted only through an Expert, so a run with no Expert behind it is refused (AB-02).
    expert_only: bool = False

    def executor_qualified(self) -> bool:
        return self.qualified is not None and self.qualified()


@dataclass(frozen=True)
class ToolResult:
    outcome: ToolOutcome
    # A tool keeps any code of its own beside the gateway's (PTOL-09).
    code: GatewayCode | str | None = None
    output: dict[str, Any] | None = None
    operation_id: str | None = None
    replayed: bool = False

    def for_model(self) -> str:
        """Codes and validated output only. A tool's own error text never reaches the model.

        The operation_id is what `complete_task` accepts as a receipt, so the model needs to see it.
        """
        reply = {"outcome": self.outcome.value, "code": self.code, "output": self.output}
        if self.operation_id is not None:
            reply["operation_id"] = self.operation_id
        return json.dumps(reply, sort_keys=True)


@dataclass
class ToolRegistry:
    _tools: dict[tuple[str, int], ToolDefinition] = field(default_factory=dict)

    def register(self, tool: ToolDefinition) -> None:
        if (
            tool.operation_class is OperationClass.ARBITRARY_EXECUTION
            and not tool.executor_qualified()
        ):
            raise ValueError("arbitrary execution stays disabled until an executor is qualified")
        if tool.operation_class in EFFECTFUL and tool.retries:
            raise ValueError("an effect is never retried blindly")
        key = (tool.tool_id, tool.version)
        if key in self._tools:
            raise ValueError(f"{tool.tool_id} v{tool.version} is already registered")
        self._tools[key] = tool

    def definitions(self) -> list[ToolDefinition]:
        return [tool for _, tool in sorted(self._tools.items())]

    def versions(self) -> dict[str, int]:
        return {tool_id: version for tool_id, version in self._tools}

    def get(self, tool_id: str, version: int) -> ToolDefinition | None:
        return self._tools.get((tool_id, version))

    def catalog(self, scope: ToolScope) -> list[dict[str, Any]]:
        """What a model may be shown: granted tools and their schemas, nothing else."""
        return [
            {
                "name": tool.tool_id,
                "version": tool.version,
                "description": tool.description,
                "input_schema": tool.input_model.model_json_schema(),
            }
            for (tool_id, version), tool in sorted(self._tools.items())
            if scope.tools.get(tool_id) == version
        ]


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


def resolve(registry: ToolRegistry, scope: ToolScope, name: str, arguments: Any) -> Call | Refused:
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


async def _target_unchanged(connection: Any, operation_id: str, target: str | None) -> bool:
    """Decision 0025 V7 and V8: an approved effect runs only against the target it was approved
    for, and an empty recorded target fails closed. One already sent, or possibly sent, is left to
    its receipt and reconciliation, as refusing it would report an effect that happened as not."""
    cursor = await connection.execute(
        "select status from app_private.tool_receipts where operation_id = %s", (operation_id,)
    )
    receipt = await cursor.fetchone()
    if receipt_may_have_sent(None if receipt is None else receipt[0]):
        return True
    approved = await approved_request(connection, operation_id)
    recorded = approved.resource_target if approved is not None else None
    return bool(recorded) and recorded == target


async def _has_approval(connection: Any, operation_id: str) -> bool:
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
    logger.log(level, event, extra={"fields": fields})


async def _expert_behind(connection: Any, scope: ToolScope) -> bool:
    """The run was admitted from an Expert's binding, the only place such a grant comes from."""
    cursor = await connection.execute(
        "select expert_id is not null from public.runs where id = %s and workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    row = await cursor.fetchone()
    return bool(row and row[0])


async def ownership_refusal(connection: Any, scope: ToolScope) -> GatewayCode | None:
    """Run status and ownership, read fresh by database time."""
    cursor = await connection.execute(
        "select r.status, j.status, j.generation, j.lease_expires_at > clock_timestamp() "
        "from public.runs r join app_private.run_jobs j on j.run_id = r.id "
        "where r.id = %s and r.workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return GatewayCode.RUN_NOT_FOUND
    run_status, job_status, generation, live = row
    if job_status != "claimed" or generation != scope.generation or not live:
        return GatewayCode.LEASE_LOST
    if run_status != RunStatus.RUNNING.value:
        return GatewayCode.RUN_NOT_RUNNING
    return None


class NotRunning(Exception):
    """The run stopped after this worker last looked, so nothing is admitted."""


async def hold_running(connection: Any, scope: ToolScope) -> None:
    """Inside the admission's transaction, so a cancel can't land between this and the receipt."""
    await hold_lease(connection, scope)
    cursor = await connection.execute(
        "select status from public.runs where id = %s for share", (scope.run_id,)
    )
    row = await cursor.fetchone()
    if row is None or row[0] != RunStatus.RUNNING.value:
        raise NotRunning


async def admission_refusal(connection: Any, scope: ToolScope, call: Call) -> GatewayCode | None:
    """The run is running and this worker owns it, then an Expert-only tool has an Expert behind
    the run (AB-02). Both are read fresh, after the call resolved and before any approval."""
    refusal = await ownership_refusal(connection, scope)
    if refusal is not None:
        return refusal
    if call.tool.expert_only and not await _expert_behind(connection, scope):
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


async def hold_for_approval(
    connection: Any, scope: ToolScope, call: Call
) -> GatewayCode | str | None:
    """None lets the call through: its policy doesn't hold it, or a person approved this operation
    and its target still resolves to the one they approved (Decision 0015, Decision 0025 V7).

    A code means it waits for a person or is refused. A tool's own code from its target resolver
    or review passes through."""
    tool, policy = call.tool, call.tool.approval
    if not policy.applies(tool.operation_class, call.parsed):
        return None
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
    if policy.target_resolver is not None and not await _target_unchanged(
        connection, call.operation_id, target
    ):
        return GatewayCode.APPROVAL_TARGET_CHANGED
    return None


async def admit_budget(
    connection: Any, scope: ToolScope, call: Call, use: int | None
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
        self, connection: Any, scope: ToolScope, name: str, arguments: Any
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
        self, connection: Any, scope: ToolScope, resolved: Call | Refused, use: int | None
    ) -> ToolResult:
        """Refused before any effect, in the order that is the gateway's security contract (SP-013):
        the call doesn't resolve, admission refuses it, it waits for a person or is refused at
        approval, or the metered budget refuses it."""
        if isinstance(resolved, Refused):
            return _denied(resolved.code)
        call = resolved
        refusal: GatewayCode | str | None = await admission_refusal(connection, scope, call)
        if refusal is None:
            refusal = await hold_for_approval(connection, scope, call)
        if refusal is None:
            refusal = await admit_budget(connection, scope, call, use)
        if refusal is not None:
            return _denied(refusal)
        if call.tool.operation_class in EFFECTFUL:
            return await self._effect(connection, scope, call)
        return await self._read(connection, scope, call)

    async def _read(self, connection: Any, scope: ToolScope, call: Call) -> ToolResult:
        """No effect, so no receipt. A repeated read must see current content."""
        tool = call.tool
        context = ToolContext(connection, scope, None)
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

    async def _effect(self, connection: Any, scope: ToolScope, call: Call) -> ToolResult:
        operation_id = call.operation_id
        context = ToolContext(connection, scope, operation_id)
        # Committed before the effect starts, so a crash leaves a record that it may have happened.
        # The lease is held for it, so a worker that stalled after its check can't admit anything.
        try:
            async with connection.transaction():
                await hold_running(connection, scope)
                cursor = await connection.execute(
                    "insert into app_private.tool_receipts (operation_id, run_id, workspace_id, "
                    "tool_id, tool_version, argument_hash, status, generation, can_readback) "
                    "values (%s, %s, %s, %s, %s, %s, 'started', %s, %s) "
                    "on conflict (operation_id) do nothing returning operation_id",
                    (
                        operation_id,
                        scope.run_id,
                        scope.workspace_id,
                        call.tool.tool_id,
                        call.tool.version,
                        call.argument_hash,
                        scope.generation,
                        call.tool.reconcile is not None,
                    ),
                )
                created = await cursor.fetchone() is not None
            if not created:
                replayed = await self._replay(context, call)
                if replayed is not None:
                    return replayed
                # A crash during this new attempt has to be classified like any other.
                async with connection.transaction():
                    await hold_running(connection, scope)
                    # A ruling covered the last attempt. Its evidence stays, but this one is open.
                    cursor = await connection.execute(
                        "update app_private.tool_receipts set status = 'started', result = null, "
                        "failure_code = null, failure_detail = null, generation = %s, "
                        "reconciled_at = null, updated_at = now() "
                        "where operation_id = %s and status <> 'succeeded' "
                        "returning operation_id",
                        (scope.generation, operation_id),
                    )
                    reopened = await cursor.fetchone() is not None
                if not reopened:
                    # A late success or a person's ruling landed since that read. Never send again.
                    replayed = await self._replay(context, call)
                    if replayed is not None:
                        return replayed
                    return _denied(GatewayCode.LEASE_LOST)
        except LeaseLost:
            return _denied(GatewayCode.LEASE_LOST)
        except NotRunning:
            return _denied(GatewayCode.RUN_NOT_RUNNING)
        return await self._attempt(context, call)

    async def _replay(self, context: ToolContext, call: Call) -> ToolResult | None:
        """The earlier outcome, if there is one. None means it failed for certain, so try again."""
        tool, operation_id = call.tool, call.operation_id
        cursor = await context.connection.execute(
            "select status, result from app_private.tool_receipts where operation_id = %s",
            (operation_id,),
        )
        status, result = await cursor.fetchone()
        if status == "succeeded":
            return ToolResult(
                ToolOutcome.SUCCEEDED, output=result, operation_id=operation_id, replayed=True
            )
        if status == "failed":
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
                await _record(context, operation_id, "succeeded", visible)
                return ToolResult(
                    ToolOutcome.SUCCEEDED, output=visible, operation_id=operation_id, replayed=True
                )
        if tool.safe_to_repeat:
            return None
        await _record(context, operation_id, "unknown", None, failure_detail=detail)
        return ToolResult(
            ToolOutcome.UNKNOWN,
            GatewayCode.OUTCOME_UNKNOWN,
            operation_id=operation_id,
            replayed=True,
        )

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
            await _record(context, call.operation_id, "failed", None, GatewayCode.LEASE_LOST)
            return ToolResult(
                ToolOutcome.DENIED, GatewayCode.LEASE_LOST, operation_id=call.operation_id
            )
        except Exception as error:  # noqa: BLE001 - an unexpected failure leaves the outcome unknown for reconciliation
            return await _unexpected_failure(context, call, error)
        if too_large:
            await _record(
                context, call.operation_id, "unknown", None, failure_detail="output_too_large"
            )
            return ToolResult(
                ToolOutcome.UNKNOWN, GatewayCode.OUTPUT_TOO_LARGE, operation_id=call.operation_id
            )
        return await _succeeded(context, call, visible)


async def _known_failure(context: ToolContext, call: Call, error: ToolFailed) -> ToolResult:
    """The tool knows the effect didn't happen, and says why with its own code and detail."""
    code = str(error) or GatewayCode.TOOL_FAILED
    detail = error.detail
    if code in GATEWAY_ONLY:
        # Only the gateway may say the lease refused an attempt: the approval gate trusts that code
        # to mean nothing was written (Decision 0025 V8).
        code, detail = GatewayCode.TOOL_FAILED, f"reserved_code:{code}"
    await _record(context, call.operation_id, "failed", None, code, detail)
    return ToolResult(ToolOutcome.FAILED, code, operation_id=call.operation_id)


async def _unexpected_failure(context: ToolContext, call: Call, error: BaseException) -> ToolResult:
    """A failure the tool didn't choose leaves the outcome unknown, for a readback or a person to
    settle. Its receipt keeps the diagnosis and its log line the cause (R-25, XERR-02)."""
    _log_failure("tool.operation.unknown", call.tool, call.operation_id, error)
    await _record(context, call.operation_id, "unknown", None, failure_detail=_diagnosis(error))
    return ToolResult(
        ToolOutcome.UNKNOWN, GatewayCode.OUTCOME_UNKNOWN, operation_id=call.operation_id
    )


async def _succeeded(context: ToolContext, call: Call, visible: dict[str, Any]) -> ToolResult:
    # The effect happened, so it is recorded whoever owns the run now.
    await _record(context, call.operation_id, "succeeded", visible)
    refusal = await ownership_refusal(context.connection, context.scope)
    if refusal is not None:
        return ToolResult(ToolOutcome.DENIED, refusal, operation_id=call.operation_id)
    return ToolResult(ToolOutcome.SUCCEEDED, output=visible, operation_id=call.operation_id)


def _visible(tool: ToolDefinition, output: BaseModel) -> tuple[dict[str, Any], bool]:
    checked = tool.output_model.model_validate(output.model_dump())
    visible = tool.redact(checked.model_dump(mode="json"))
    return visible, len(json.dumps(visible).encode()) > tool.max_output_bytes


async def _record(
    context: ToolContext,
    operation_id: str,
    status: str,
    result: dict[str, Any] | None,
    failure_code: str | None = None,
    failure_detail: str | None = None,
) -> None:
    """Only moves a receipt forward. A success is recorded whoever owns the run now, as the effect
    happened, even over a ruling that it hadn't: repeating it would be the worse mistake, and the
    ruling's evidence stays. Anything else speaks only for the attempt on record."""
    values = (
        status,
        json.dumps(result) if result is not None else None,
        failure_code,
        failure_detail,
        operation_id,
    )
    if status == "succeeded":
        await context.connection.execute(
            "update app_private.tool_receipts set status = %s, result = %s, failure_code = %s, "
            "failure_detail = %s, updated_at = now() "
            "where operation_id = %s and status <> 'succeeded'",
            values,
        )
        return
    await context.connection.execute(
        "update app_private.tool_receipts set status = %s, result = %s, failure_code = %s, "
        "failure_detail = %s, updated_at = now() "
        "where operation_id = %s and status = 'started' and generation <= %s",
        (*values, context.scope.generation),
    )
