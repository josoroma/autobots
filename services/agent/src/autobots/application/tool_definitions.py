"""What a tool is, what it is handed and what it returns: the vocabulary every tool module and the
gateway share (PTOL-07). Building the full set of tools is the composition edge's job
(adapters/tool_registry.py, XMOD-01); nothing in application/ imports it.
"""

import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from autobots.application import tool_keys
from autobots.application.approvals import ApprovedRequest
from autobots.application.approvals import return_to_review as send_back_to_review
from autobots.application.run_usage import RootLimits
from autobots.application.sql import SqlConnection
from autobots.domain.stops import GatewayCode
from autobots.domain.tool_catalog import CostClass, KeyRequirement, ToolGroup, ToolProvider
from autobots.domain.tools import EFFECTFUL, OperationClass, ToolOutcome

if TYPE_CHECKING:
    from autobots.application.artifacts import ObjectStore
    from autobots.application.assignments import Delegation
    from autobots.application.browsing_tool import BrowsingRuntime


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


class ToolFailed(Exception):
    """The tool knows the effect did not happen. Anything else raised leaves the outcome unknown.

    `detail` is for diagnosis only: a category the tool chose, never text the model wrote. It's
    stored on the receipt and doesn't reach the model.
    """

    def __init__(self, *args: object, detail: str | None = None) -> None:
        super().__init__(*args)
        self.detail = detail


class RuntimeUnbound(ToolFailed):
    """A definition built with no runtime, as the catalog describes it, refuses every call before
    any effect (XMOD-01, PTOL-08). A worker's pass binds the runtime its tools use."""

    def __init__(self) -> None:
        super().__init__("tool_runtime_unbound")


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
    """What a tool's handler, readback, target resolver and review are handed.

    Application tools read and write the tables they own through `connection`. External adapters
    never read it, which tests/test_effect_writers.py checks (XMOD-02): they use the capabilities,
    `approval` and `return_to_review`, and `key` and `setting` for this attempt's Keys & vars."""

    connection: SqlConnection
    scope: ToolScope
    operation_id: str | None
    # What a person approved for this dispatch, loaded once the approval gate released the call,
    # and None when no approval held it (XMOD-02).
    approval: ApprovedRequest | None = None

    async def return_to_review(self, tool_id: str, detail: dict[str, Any]) -> UUID | None:
        """Nothing was sent, so this operation's approved request goes back to a person with
        `detail`, under this attempt's lease (approvals.return_to_review, Decision 0022 D15).
        None when it has no approved request, or no operation."""
        if self.operation_id is None:
            return None
        return await send_back_to_review(
            self.connection,
            self.scope,
            operation_id=self.operation_id,
            tool_id=tool_id,
            detail=detail,
        )

    async def setting(self, name: str, environ: Mapping[str, str]) -> str | None:
        """This attempt's value of the Keys & vars item `name` for the run's workspace, by
        `tool_keys.resolve`'s order (PRD-Tool-Catalog PK-01, Decisions 0024 and 0025). A saved
        secret is unsealed for this call only and goes to the caller alone. None when no source
        has one. A saved secret that can't be unsealed refuses the call as
        `<credential>_key_unavailable`, and never falls through to the environment."""
        try:
            return await tool_keys.attempt_value(
                self.connection, self.scope.workspace_id, tool_keys.ITEMS[name], environ
            )
        except tool_keys.ToolKeyUnavailable as error:
            raise ToolFailed(error.code) from None

    async def key(self, name: str, environ: Mapping[str, str]) -> str:
        """`setting` for a key the call can't do without: a missing one refuses the call as
        `<credential>_key_missing`, naming no value."""
        value = await self.setting(name, environ)
        if value is None:
            raise ToolFailed(
                tool_keys.ToolKeyMissing(tool_keys.ITEMS[name].credential or name).code
            )
        return value


Handler = Callable[[Any, ToolContext], Awaitable[BaseModel]]
Reconcile = Callable[[Any, ToolContext], Awaitable[BaseModel | None]]


async def refuse_unbound(_arguments: object, _context: ToolContext) -> BaseModel:
    """The handler a definition built with no runtime runs: it refuses before any effect."""
    raise RuntimeUnbound


# Decision 0015. Change it whenever ApprovalPolicy's condition, rule or reason text changes, so a
# request names the rules it was held under. The pin test in test_tools.py fails until it changes.
# Version 2 adds a tool's per-call condition, ApprovalPolicy's `when` (Decision 0026 C3).
APPROVAL_POLICY_VERSION = "approval-policy/2"


def _no_target(_: object) -> str | None:
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
    # Decision 0035 Y2: when this holds for a call, read at the call, it starts without approval.
    # A consequential external write never takes it (`waivable`).
    waived: Callable[[ToolContext], Awaitable[bool]] | None = None

    def _every_call(self, operation_class: OperationClass) -> bool:
        return self.always or operation_class is OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE

    def applies(self, operation_class: OperationClass, parsed: object) -> bool:
        """Whether this call, with these parsed arguments, waits for a person."""
        return self._every_call(operation_class) or (self.when is not None and self.when(parsed))

    def waivable(self, operation_class: OperationClass) -> bool:
        """Whether a waiver may release a call of this class (Decision 0035 Y2)."""
        return (
            self.waived is not None
            and operation_class is not OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE
        )

    def label(
        self, operation_class: OperationClass
    ) -> Literal["always", "unless_yolo", "by_action", "never"]:
        """How the catalog shows the policy (Decision 0026 C9, Decision 0035 Y2)."""
        if self._every_call(operation_class):
            return "unless_yolo" if self.waivable(operation_class) else "always"
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
    # Public fields read from the call's context rather than its arguments, added to the tool row's
    # public input when it is recorded, such as browsing's `typing` (Decision 0035 Y2).
    public_context: Callable[[ToolContext], Awaitable[Mapping[str, Any]]] | None = None
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


@dataclass(frozen=True)
class ToolRuntime:
    """What one pass binds its tools to: its limits, the artifact store and how its children are
    driven. A definition whose part is missing, as the catalog builds every one, still describes
    itself, and its handler refuses before any effect (XMOD-01, PTOL-08)."""

    limits: RootLimits
    object_store: "ObjectStore | None" = None
    delegation: "Delegation | None" = None


@dataclass(frozen=True)
class Browsing:
    """`browse_goal` as a pass or the catalog may have it (AB-02, Decision 0025 V6). It is
    registered only when the worker's binder or the catalog passes one, which each does only while
    browsing is switched on and qualified, and `qualified` is read again at each call. `runtime` is
    the executor and the run's researcher route a worker bound for this job; without one, a call
    refuses before any container starts."""

    qualified: Callable[[], bool]
    runtime: "BrowsingRuntime | None" = None


class ToolSet(Protocol):
    """Every tool a pass, a workflow or the catalog is built with (PRD-Tool-Catalog TC-01). The
    composition edge provides it, adapters/tool_registry.build_registry, so the catalog and the
    worker list the same tools. With no runtime, each definition describes itself."""

    def __call__(
        self,
        runtime: ToolRuntime | None,
        *,
        workflow: bool = False,
        browsing: Browsing | None = None,
    ) -> ToolRegistry: ...
