"""The one place a tool runs. Every check happens before the effect, SP-013 and PRD 9.1."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError

from autobots.application.approvals import approval_gate, scope_hash, scope_snapshot
from autobots.application.runs import LeaseLost
from autobots.domain.runs import RunStatus
from autobots.domain.tool_catalog import CostClass, KeyRequirement, ToolGroup, ToolProvider
from autobots.domain.tools import EFFECTFUL, OperationClass, ToolOutcome, path_granted


class NotDelivered(Exception):
    """A readback found the effect never reached the destination, so one new attempt is safe."""


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
    approval_required: bool = False
    # What a reviewer is told this touches, from the arguments or server configuration.
    resource_target: Callable[[Any], str | None] = lambda _: None
    # Why policy asks, when this tool has a reason of its own. Never from the model.
    approval_reason: str | None = None
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
    # PRD-Studio GH-06: what the reviewer sees beyond the arguments, read before the approval
    # request exists. It may read the destination, never write it.
    review_detail: Callable[[Any], Awaitable[dict[str, Any]]] | None = None
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
    code: str | None = None
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


# Decision 0015. Change it whenever `_approval_rule`, `_approval_reason` or the condition that asks
# for approval changes, so a request names the rules it was held under. A unit test pins it.
APPROVAL_POLICY_VERSION = "approval-policy/1"


def _approval_rule(tool: ToolDefinition) -> str:
    """Which of the policy's rules held this call."""
    if tool.operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE:
        return "consequential_external_write"
    return "tool_marked"


def _approval_reason(tool: ToolDefinition) -> str:
    """Fixed text from this tool's policy, so nothing a model wrote can reach it."""
    if tool.approval_reason is not None:
        return tool.approval_reason
    if tool.operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE:
        return (
            "This tool changes something outside this Mac, so policy holds each call for a person."
        )
    return "This tool is marked to wait for a person, so policy holds each call."


def _operation_id(scope: ToolScope, tool: ToolDefinition, parsed: BaseModel) -> str:
    # Two foreach items can be equal and still be two pieces of work.
    place = f"|{scope.instance}" if scope.instance else ""
    identity = f"{scope.run_id}{place}|{tool.tool_id}|{tool.version}|{_hash(parsed)}"
    return hashlib.sha256(identity.encode()).hexdigest()


async def _has_approval(connection: Any, operation_id: str) -> bool:
    cursor = await connection.execute(
        "select 1 from public.approval_requests where operation_id = %s", (operation_id,)
    )
    return await cursor.fetchone() is not None


def _denied(code: str) -> ToolResult:
    return ToolResult(ToolOutcome.DENIED, code)


async def _expert_behind(connection: Any, scope: ToolScope) -> bool:
    """The run was admitted from an Expert's binding, the only place such a grant comes from."""
    cursor = await connection.execute(
        "select expert_id is not null from public.runs where id = %s and workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    row = await cursor.fetchone()
    return bool(row and row[0])


async def ownership_refusal(connection: Any, scope: ToolScope) -> str | None:
    """Run status and ownership, read fresh by database time."""
    cursor = await connection.execute(
        "select r.status, j.status, j.generation, j.lease_expires_at > clock_timestamp() "
        "from public.runs r join app_private.run_jobs j on j.run_id = r.id "
        "where r.id = %s and r.workspace_id = %s",
        (scope.run_id, scope.workspace_id),
    )
    row = await cursor.fetchone()
    if row is None:
        return "run_not_found"
    run_status, job_status, generation, live = row
    if job_status != "claimed" or generation != scope.generation or not live:
        return "lease_lost"
    if run_status != RunStatus.RUNNING.value:
        return "run_not_running"
    return None


async def hold_lease(connection: Any, scope: ToolScope) -> None:
    """Inside a write's transaction. The share lock serializes it against a new claim."""
    cursor = await connection.execute(
        "select 1 from app_private.run_jobs where run_id = %s and generation = %s "
        "and status = 'claimed' and lease_expires_at > clock_timestamp() for share",
        (scope.run_id, scope.generation),
    )
    if await cursor.fetchone() is None:
        raise LeaseLost("this worker no longer owns the run")


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


@dataclass(frozen=True)
class ToolGateway:
    registry: ToolRegistry

    async def execute(
        self, connection: Any, scope: ToolScope, name: str, arguments: Any
    ) -> ToolResult:
        """Every dispatch is recorded, denials included, before and after it runs (TU-01). A worker
        that lost its lease records nothing, and is refused below as before."""
        from autobots.application.tool_uses import begin_use, complete_use

        use = await begin_use(connection, scope, self.registry, name, arguments)
        result = await self._dispatch(connection, scope, name, arguments, use)
        if use is not None:
            # A call now waiting for a person released the lease in its own approval gate.
            waiting = result.code == "approval_pending"
            await complete_use(
                connection, scope, self.registry, use, name, result, fenced=not waiting
            )
        return result

    async def _dispatch(
        self, connection: Any, scope: ToolScope, name: str, arguments: Any, use: int | None
    ) -> ToolResult:
        """Refused before any effect: ungranted, unqualified, invalid, out of scope or unowned."""
        version = scope.tools.get(name)
        if version is None:
            return _denied("tool_not_granted")
        tool = self.registry.get(name, version)
        if tool is None:
            return _denied("tool_not_registered")
        if (
            tool.operation_class is OperationClass.ARBITRARY_EXECUTION
            and not tool.executor_qualified()
        ):
            # Checked again here, as a qualification can be withdrawn while a worker runs.
            return _denied("capability_disabled")
        try:
            parsed = tool.input_model.model_validate(arguments)
        except ValidationError:
            return _denied("invalid_arguments")
        if not all(path_granted(path, scope.paths) for path in tool.resources(parsed)):
            return _denied("resource_not_granted")
        refusal = await ownership_refusal(connection, scope)
        if refusal is not None:
            return _denied(refusal)
        if tool.expert_only and not await _expert_behind(connection, scope):
            return _denied("expert_grant_required")
        if tool.approval_required or (
            tool.operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE
        ):
            detail = None
            if tool.review_detail is not None and not await _has_approval(
                connection, _operation_id(scope, tool, parsed)
            ):
                try:
                    detail = await asyncio.wait_for(
                        tool.review_detail(parsed), tool.timeout_seconds
                    )
                except ToolFailed as error:
                    return _denied(str(error) or "review_unavailable")
                except Exception:
                    return _denied("review_unavailable")
            code = await approval_gate(
                connection,
                workspace_id=scope.workspace_id,
                run_id=scope.run_id,
                generation=scope.generation,
                operation_id=_operation_id(scope, tool, parsed),
                tool_id=tool.tool_id,
                tool_version=tool.version,
                operation_class=tool.operation_class.value,
                argument_hash=_hash(parsed),
                arguments=tool.redact(parsed.model_dump(mode="json")),
                current_scope_hash=scope_hash(scope.tools, scope.paths),
                policy_reason=_approval_reason(tool),
                resource_target=tool.resource_target(parsed),
                scope=scope_snapshot(scope.tools, scope.paths),
                policy_version=APPROVAL_POLICY_VERSION,
                policy_rule=_approval_rule(tool),
                review_detail=detail,
            )
            if code is not None:
                return _denied(code)
        if tool.cost_class is CostClass.METERED_PROVIDER:
            # Decision 0017 Q4: counted per root run tree, before any request leaves. After
            # approval, so a call waiting for a person isn't counted twice.
            from autobots.application.tool_uses import admit_metered

            if use is None or not await admit_metered(connection, scope, use):
                return _denied("tool_budget_exceeded")
        if tool.operation_class in EFFECTFUL:
            return await self._effect(connection, scope, tool, parsed)
        return await self._read(connection, scope, tool, parsed)

    async def _read(
        self, connection: Any, scope: ToolScope, tool: ToolDefinition, parsed: BaseModel
    ) -> ToolResult:
        """No effect, so no receipt. A repeated read must see current content."""
        context = ToolContext(connection, scope, None)
        for attempt in range(tool.retries + 1):
            try:
                output = await asyncio.wait_for(tool.handler(parsed, context), tool.timeout_seconds)
            except TimeoutError:
                code = "tool_timeout"
            except ToolFailed as error:
                return ToolResult(ToolOutcome.FAILED, str(error) or "tool_failed")
            except Exception:
                code = "tool_failed"
            else:
                visible, too_large = _visible(tool, output)
                if too_large:
                    return ToolResult(ToolOutcome.FAILED, "output_too_large")
                return ToolResult(ToolOutcome.SUCCEEDED, output=visible)
            if attempt < tool.retries:
                refusal = await ownership_refusal(connection, scope)
                if refusal is not None:
                    return _denied(refusal)
        return ToolResult(ToolOutcome.FAILED, code)

    async def _effect(
        self, connection: Any, scope: ToolScope, tool: ToolDefinition, parsed: BaseModel
    ) -> ToolResult:
        argument_hash = _hash(parsed)
        operation_id = _operation_id(scope, tool, parsed)
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
                        tool.tool_id,
                        tool.version,
                        argument_hash,
                        scope.generation,
                        tool.reconcile is not None,
                    ),
                )
                created = await cursor.fetchone() is not None
            if not created:
                replayed = await self._replay(context, tool, parsed, operation_id)
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
                    replayed = await self._replay(context, tool, parsed, operation_id)
                    if replayed is not None:
                        return replayed
                    return _denied("lease_lost")
        except LeaseLost:
            return _denied("lease_lost")
        except NotRunning:
            return _denied("run_not_running")
        return await self._attempt(context, tool, parsed, operation_id)

    async def _replay(
        self, context: ToolContext, tool: ToolDefinition, parsed: BaseModel, operation_id: str
    ) -> ToolResult | None:
        """The earlier outcome, if there is one. None means it failed for certain, so try again."""
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
        if tool.reconcile is not None:
            try:
                found = await asyncio.wait_for(
                    tool.reconcile(parsed, context), tool.timeout_seconds
                )
            except NotDelivered:
                return None
            except Exception:
                found = None
            if found is not None:
                visible, _ = _visible(tool, found)
                await _record(context, operation_id, "succeeded", visible)
                return ToolResult(
                    ToolOutcome.SUCCEEDED, output=visible, operation_id=operation_id, replayed=True
                )
        if tool.safe_to_repeat:
            return None
        await _record(context, operation_id, "unknown", None)
        return ToolResult(
            ToolOutcome.UNKNOWN, "outcome_unknown", operation_id=operation_id, replayed=True
        )

    async def _attempt(
        self, context: ToolContext, tool: ToolDefinition, parsed: BaseModel, operation_id: str
    ) -> ToolResult:
        try:
            output = await asyncio.wait_for(tool.handler(parsed, context), tool.timeout_seconds)
        except ToolFailed as error:
            code = str(error) or "tool_failed"
            await _record(context, operation_id, "failed", None, code, error.detail)
            return ToolResult(ToolOutcome.FAILED, code, operation_id=operation_id)
        except LeaseLost:
            # The write's transaction refused it, so nothing happened.
            await _record(context, operation_id, "failed", None)
            return ToolResult(ToolOutcome.DENIED, "lease_lost", operation_id=operation_id)
        except Exception:
            await _record(context, operation_id, "unknown", None)
            return ToolResult(ToolOutcome.UNKNOWN, "outcome_unknown", operation_id=operation_id)
        visible, too_large = _visible(tool, output)
        if too_large:
            await _record(context, operation_id, "unknown", None)
            return ToolResult(ToolOutcome.UNKNOWN, "output_too_large", operation_id=operation_id)
        # The effect happened, so it is recorded whoever owns the run now.
        await _record(context, operation_id, "succeeded", visible)
        refusal = await ownership_refusal(context.connection, context.scope)
        if refusal is not None:
            return ToolResult(ToolOutcome.DENIED, refusal, operation_id=operation_id)
        return ToolResult(ToolOutcome.SUCCEEDED, output=visible, operation_id=operation_id)


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
