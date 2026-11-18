"""Why a pass stopped, what that does to its run, and what a tool call's code does to the loop.

`StopCode` is a reason, stored as `app_private.run_usage.stop_reason` and returned as a pass's
code. It is never a second run state: the run's state stays `RunStatus`, moved by the command each
`Disposition` names. Every value is the string already stored, so nothing persisted changes. Public
DTOs keep their own `str` fields (PRUN-02).

A failed run can never resume (SP-010), so every known code has an explicit disposition below, and
a code missing from the table suspends the run instead of failing it (Decision 0028 E3).
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from autobots.domain.execution import INCOMPATIBLE
from autobots.domain.runs import RunCommand


class _Code(StrEnum):
    """A stored string with a name. It prints as that string, in a tuple too, so evidence that
    shows a code reads the same as before the names existed."""

    def __repr__(self) -> str:
        return repr(self.value)


class Disposition(_Code):
    """What a pass's stop does to its run."""

    # Nothing stopped it, so its candidate goes to verification.
    VERIFY = "verify"
    # Paused and resumable: a person adds budget or a key, reconciles a call or resumes the run.
    SUSPEND = "suspend"
    # Failed, which nobody can resume (SP-010).
    FAIL = "fail"
    # Not this worker's to decide: another owner, a person's pause or a pending approval has it.
    RELEASE = "release"


# Its docstring is the StopCode schema's description in the OpenAPI document (contracts/runs.py).
class StopCode(_Code):
    """Why a run's pass stopped: each code a pass can stop with, and those the cancel settlement
    writes. One other stored form exists, a spent repair: `repair_limit:` followed by the
    repairable code, such as `repair_limit:plan_out_of_scope`."""

    # FailureClass values, from a model call or a refusal before dispatch (model_attempts.py).
    CREDENTIALS_REQUIRED = "credentials_required"
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    COST_UNAVAILABLE = "cost_unavailable"
    INVALID_CREDENTIAL = "invalid_credential"
    INSUFFICIENT_CREDITS = "insufficient_credits"
    RATE_LIMITED = "rate_limited"
    PROVIDER_ERROR = "provider_error"
    NETWORK_BEFORE_ACCEPTANCE = "network_before_acceptance"
    PARTIAL_STREAM = "partial_stream"
    UNCERTAIN_ACCEPTANCE = "uncertain_acceptance"
    INCOMPLETE_OUTPUT = "incomplete_output"
    OTHER = "other"
    # AdmissionRefused codes; COST_UNAVAILABLE above is CostUnavailable's (model_admission.py).
    ADMISSION_REFUSED = "admission_refused"
    BUDGET_EXCEEDED = "budget_exceeded"
    NO_INFERENCE_SLOT = "no_inference_slot"
    # The loop's own model-call gates (goal_loop.py, application/loop_admission.py).
    UNCERTAIN_MODEL_CALL = "uncertain_model_call"
    UNADMITTED_MODEL_CALL = "unadmitted_model_call"
    REQUEST_UNENCODABLE = "request_unencodable"
    ROUTE_NOT_BOUND = "route_not_bound"
    COMPACTION_FAILED = "compaction_failed"
    INCOMPATIBLE_VERSION = INCOMPATIBLE
    # LimitReached codes, one per counter (run_usage.py), and the loop's other bounds.
    MODEL_CALLS_LIMIT = "model_calls_limit"
    TOOL_DISPATCHES_LIMIT = "tool_dispatches_limit"
    REPAIRS_LIMIT = "repairs_limit"
    PLAN_REVISIONS_LIMIT = "plan_revisions_limit"
    CHILDREN_LIMIT = "children_limit"
    ACTIVE_TIME_LIMIT = "active_time_limit"
    STEP_LIMIT = "step_limit"
    # Ownership, waits and tool results, from the gateway and assignments (GatewayCode below).
    LEASE_LOST = "lease_lost"
    RUN_NOT_RUNNING = "run_not_running"
    RUN_NOT_FOUND = "run_not_found"
    APPROVAL_PENDING = "approval_pending"
    PARENT_NOT_RUNNING = "parent_not_running"
    ASSIGNMENT_PAUSED = "assignment_paused"
    ASSIGNMENT_LOST = "assignment_lost"
    ASSIGNMENT_BUSY = "assignment_busy"
    OUTCOME_UNKNOWN = "outcome_unknown"
    OUTPUT_TOO_LARGE = "output_too_large"
    # The transition `run_lifecycle.finish` applied was refused under the run's row lock. Never
    # stored, since the transaction that would store it rolls back (R-34, PRUN-03).
    COMMAND_REFUSED = "command_refused"
    # Passes kept raising an exception no handler classifies until the bound, so the run is
    # suspended (run_lifecycle.record_failure, Decision 0028 E4).
    WORKER_FAILED = "worker_failed"
    # The plan and verification's verdict (run_lifecycle.decide and settlement.py).
    PLAN_MISSING = "plan_missing"
    PLAN_INCOMPLETE = "plan_incomplete"
    CRITERIA_UNMET = "criteria_unmet"
    # A workflow's own ends (workflow_runner.py).
    WORKFLOW_INVALID = "workflow_invalid"
    WORKFLOW_NODE_FAILED = "workflow_node_failed"
    WORKFLOW_STALLED = "workflow_stalled"
    # Written by the cancel settlement once the run's fate is decided (SETTLEMENT below).
    CANCELLED = "cancelled"
    CANCELLED_WITH_UNKNOWN_OUTCOMES = "cancelled_with_unknown_outcomes"
    CHILDREN_SETTLING = "children_settling"


# Each code's disposition, as `run_lifecycle.decide` applies it. tests/test_stop_codes.py holds it
# equal to the sets it replaced, so a change here is a behavior change and needs its own decision
# (R-29).
DISPOSITION: Final[Mapping[StopCode, Disposition]] = MappingProxyType(
    {
        # Waiting can resolve these: a person adds budget or a key, or reconciles an uncertain call.
        StopCode.BUDGET_EXCEEDED: Disposition.SUSPEND,
        StopCode.NO_INFERENCE_SLOT: Disposition.SUSPEND,
        StopCode.COST_UNAVAILABLE: Disposition.SUSPEND,
        StopCode.CREDENTIALS_REQUIRED: Disposition.SUSPEND,
        StopCode.CREDENTIAL_UNAVAILABLE: Disposition.SUSPEND,
        StopCode.MODEL_UNAVAILABLE: Disposition.SUSPEND,
        StopCode.NETWORK_BEFORE_ACCEPTANCE: Disposition.SUSPEND,
        StopCode.INVALID_CREDENTIAL: Disposition.SUSPEND,
        StopCode.INSUFFICIENT_CREDITS: Disposition.SUSPEND,
        StopCode.PARTIAL_STREAM: Disposition.SUSPEND,
        StopCode.UNCERTAIN_ACCEPTANCE: Disposition.SUSPEND,
        StopCode.UNCERTAIN_MODEL_CALL: Disposition.SUSPEND,
        StopCode.ASSIGNMENT_PAUSED: Disposition.SUSPEND,
        StopCode.ASSIGNMENT_LOST: Disposition.SUSPEND,
        StopCode.ASSIGNMENT_BUSY: Disposition.SUSPEND,
        StopCode.PARENT_NOT_RUNNING: Disposition.SUSPEND,
        StopCode.OUTCOME_UNKNOWN: Disposition.SUSPEND,
        # A saved run waits for a release that can continue it (PRD-LangChain-Deep-Agents 10.3).
        StopCode.INCOMPATIBLE_VERSION: Disposition.SUSPEND,
        # A worker on another model, say after a release, leaves the saved run for the right one.
        StopCode.ROUTE_NOT_BOUND: Disposition.SUSPEND,
        # A defect that retries didn't ride out waits for a person, who can resume it (Decision 0028
        # E4).
        StopCode.WORKER_FAILED: Disposition.SUSPEND,
        # Another owner, a person's pause or cancel, or a pending approval has the run.
        StopCode.LEASE_LOST: Disposition.RELEASE,
        StopCode.RUN_NOT_RUNNING: Disposition.RELEASE,
        StopCode.RUN_NOT_FOUND: Disposition.RELEASE,
        StopCode.APPROVAL_PENDING: Disposition.RELEASE,
        # A person's pause or cancel moved the run after `finish` looked, so nothing was written
        # and the run is theirs (R-34).
        StopCode.COMMAND_REFUSED: Disposition.RELEASE,
        # Retries, limits and refusals that waiting would not change.
        StopCode.RATE_LIMITED: Disposition.FAIL,
        StopCode.PROVIDER_ERROR: Disposition.FAIL,
        StopCode.INCOMPLETE_OUTPUT: Disposition.FAIL,
        StopCode.OTHER: Disposition.FAIL,
        StopCode.ADMISSION_REFUSED: Disposition.FAIL,
        StopCode.UNADMITTED_MODEL_CALL: Disposition.FAIL,
        StopCode.REQUEST_UNENCODABLE: Disposition.FAIL,
        StopCode.COMPACTION_FAILED: Disposition.FAIL,
        StopCode.MODEL_CALLS_LIMIT: Disposition.FAIL,
        StopCode.TOOL_DISPATCHES_LIMIT: Disposition.FAIL,
        StopCode.REPAIRS_LIMIT: Disposition.FAIL,
        StopCode.PLAN_REVISIONS_LIMIT: Disposition.FAIL,
        StopCode.CHILDREN_LIMIT: Disposition.FAIL,
        StopCode.ACTIVE_TIME_LIMIT: Disposition.FAIL,
        StopCode.STEP_LIMIT: Disposition.FAIL,
        # Its result is unknown, so nothing should build on it.
        StopCode.OUTPUT_TOO_LARGE: Disposition.FAIL,
        StopCode.PLAN_MISSING: Disposition.FAIL,
        StopCode.PLAN_INCOMPLETE: Disposition.FAIL,
        StopCode.CRITERIA_UNMET: Disposition.FAIL,
        StopCode.WORKFLOW_INVALID: Disposition.FAIL,
        StopCode.WORKFLOW_NODE_FAILED: Disposition.FAIL,
        StopCode.WORKFLOW_STALLED: Disposition.FAIL,
    }
)
# The cancel settlement writes these after deciding the run's fate, so no stop is routed by them.
SETTLEMENT: Final = frozenset(
    {StopCode.CANCELLED, StopCode.CANCELLED_WITH_UNKNOWN_OUTCOMES, StopCode.CHILDREN_SETTLING}
)
# A code missing from the table: paused and resumable, and logged by its caller (Decision 0028 E3).
UNMAPPED: Final = Disposition.SUSPEND
# The command each disposition applies. RELEASE applies none.
COMMANDS: Final[Mapping[Disposition, RunCommand]] = MappingProxyType(
    {
        Disposition.VERIFY: RunCommand.VERIFY,
        Disposition.SUSPEND: RunCommand.SUSPEND,
        Disposition.FAIL: RunCommand.FAIL,
    }
)


def _with(disposition: Disposition) -> frozenset[StopCode]:
    return frozenset(code for code, chosen in DISPOSITION.items() if chosen is disposition)


PAUSE_FOR: Final = _with(Disposition.SUSPEND)
NOT_OURS: Final = _with(Disposition.RELEASE)


class GatewayCode(_Code):
    """A code a tool call's result carries: the gateway's own, and those a tool returns that the
    loops route on. A tool keeps any other code of its own as a plain string (PTOL-09)."""

    # The gateway's refusals before any effect (tool_gateway.py).
    TOOL_NOT_GRANTED = "tool_not_granted"
    TOOL_NOT_REGISTERED = "tool_not_registered"
    CAPABILITY_DISABLED = "capability_disabled"
    INVALID_ARGUMENTS = "invalid_arguments"
    RESOURCE_NOT_GRANTED = "resource_not_granted"
    EXPERT_GRANT_REQUIRED = "expert_grant_required"
    CONNECTOR_NOT_CONFIGURED = "connector_not_configured"
    REVIEW_UNAVAILABLE = "review_unavailable"
    APPROVAL_TARGET_CHANGED = "approval_target_changed"
    TOOL_BUDGET_EXCEEDED = "tool_budget_exceeded"
    # The owner turned the tool, or its group, off for the workspace (Decision 0033 W2).
    TOOL_TURNED_OFF = "tool_turned_off"
    # Run status and ownership, read fresh (tool_gateway.ownership_refusal).
    RUN_NOT_FOUND = "run_not_found"
    LEASE_LOST = "lease_lost"
    RUN_NOT_RUNNING = "run_not_running"
    # The approval gate (approvals.approval_gate).
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_SCOPE_CHANGED = "approval_scope_changed"
    APPROVAL_CONSUMED = "approval_consumed"
    APPROVAL_REJECTED = "approval_rejected"
    # How a call ended (tool_gateway.py).
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_FAILED = "tool_failed"
    OUTPUT_TOO_LARGE = "output_too_large"
    OUTCOME_UNKNOWN = "outcome_unknown"
    # An assignment's own codes (assignments.py).
    ASSIGNMENT_DEPTH_LIMIT = "assignment_depth_limit"
    ROUTE_NOT_GRANTED = "route_not_granted"
    SCOPE_EXPANSION_DENIED = "scope_expansion_denied"
    PARENT_NOT_RUNNING = "parent_not_running"
    OUTSTANDING_ASSIGNMENTS_LIMIT = "outstanding_assignments_limit"
    CHILDREN_LIMIT = "children_limit"
    ASSIGNMENT_BUSY = "assignment_busy"
    ASSIGNMENT_PAUSED = "assignment_paused"
    ASSIGNMENT_LOST = "assignment_lost"
    # The plan tools' codes (plans.py).
    PLAN_REVISIONS_LIMIT = "plan_revisions_limit"
    PLAN_DUPLICATE_TASK = "plan_duplicate_task"
    PLAN_UNKNOWN_DEPENDENCY = "plan_unknown_dependency"
    PLAN_CYCLE = "plan_cycle"
    PLAN_OUT_OF_SCOPE = "plan_out_of_scope"
    PLAN_UNCOVERED_CRITERIA = "plan_uncovered_criteria"
    PLAN_DROPS_COMPLETED = "plan_drops_completed"
    PLAN_CHANGES_COMPLETED = "plan_changes_completed"
    PLAN_REASON_REQUIRED = "plan_reason_required"
    PLAN_MISSING = "plan_missing"
    TASK_UNKNOWN = "task_unknown"
    TASK_DEPENDENCIES_OPEN = "task_dependencies_open"
    EVIDENCE_INVALID = "evidence_invalid"


class ToolRouting(_Code):
    """What the goal loop does when a tool call's result carries a code."""

    # The pass stops, with the code as its stop code.
    STOP = "stop"
    # The model may correct the call, spending the root's single repair.
    REPAIR = "repair"
    # The model reads the result and carries on.
    SHOW = "show"


ROUTING: Final[Mapping[GatewayCode, ToolRouting]] = MappingProxyType(
    {
        GatewayCode.LEASE_LOST: ToolRouting.STOP,
        GatewayCode.RUN_NOT_RUNNING: ToolRouting.STOP,
        GatewayCode.APPROVAL_PENDING: ToolRouting.STOP,
        GatewayCode.OUTCOME_UNKNOWN: ToolRouting.STOP,
        # Its result is unknown, so nothing should build on it.
        GatewayCode.OUTPUT_TOO_LARGE: ToolRouting.STOP,
        GatewayCode.ASSIGNMENT_BUSY: ToolRouting.STOP,
        GatewayCode.ASSIGNMENT_PAUSED: ToolRouting.STOP,
        GatewayCode.ASSIGNMENT_LOST: ToolRouting.STOP,
        GatewayCode.PLAN_REVISIONS_LIMIT: ToolRouting.STOP,
        GatewayCode.INVALID_ARGUMENTS: ToolRouting.REPAIR,
        GatewayCode.ROUTE_NOT_GRANTED: ToolRouting.REPAIR,
        GatewayCode.SCOPE_EXPANSION_DENIED: ToolRouting.REPAIR,
        GatewayCode.PLAN_DUPLICATE_TASK: ToolRouting.REPAIR,
        GatewayCode.PLAN_UNKNOWN_DEPENDENCY: ToolRouting.REPAIR,
        GatewayCode.PLAN_CYCLE: ToolRouting.REPAIR,
        GatewayCode.PLAN_OUT_OF_SCOPE: ToolRouting.REPAIR,
        GatewayCode.PLAN_UNCOVERED_CRITERIA: ToolRouting.REPAIR,
        GatewayCode.PLAN_DROPS_COMPLETED: ToolRouting.REPAIR,
        GatewayCode.PLAN_CHANGES_COMPLETED: ToolRouting.REPAIR,
        GatewayCode.PLAN_REASON_REQUIRED: ToolRouting.REPAIR,
        GatewayCode.PLAN_MISSING: ToolRouting.REPAIR,
        GatewayCode.TASK_UNKNOWN: ToolRouting.REPAIR,
        GatewayCode.TASK_DEPENDENCIES_OPEN: ToolRouting.REPAIR,
        GatewayCode.EVIDENCE_INVALID: ToolRouting.REPAIR,
        # The next dispatch's guard stops the pass with run_not_running, so these are only shown.
        GatewayCode.RUN_NOT_FOUND: ToolRouting.SHOW,
        GatewayCode.PARENT_NOT_RUNNING: ToolRouting.SHOW,
        GatewayCode.TOOL_NOT_GRANTED: ToolRouting.SHOW,
        GatewayCode.TOOL_NOT_REGISTERED: ToolRouting.SHOW,
        GatewayCode.CAPABILITY_DISABLED: ToolRouting.SHOW,
        GatewayCode.RESOURCE_NOT_GRANTED: ToolRouting.SHOW,
        GatewayCode.EXPERT_GRANT_REQUIRED: ToolRouting.SHOW,
        GatewayCode.CONNECTOR_NOT_CONFIGURED: ToolRouting.SHOW,
        GatewayCode.REVIEW_UNAVAILABLE: ToolRouting.SHOW,
        GatewayCode.APPROVAL_TARGET_CHANGED: ToolRouting.SHOW,
        GatewayCode.TOOL_BUDGET_EXCEEDED: ToolRouting.SHOW,
        # The model sees the tool is off and plans without it (Decision 0033 W2).
        GatewayCode.TOOL_TURNED_OFF: ToolRouting.SHOW,
        GatewayCode.APPROVAL_EXPIRED: ToolRouting.SHOW,
        GatewayCode.APPROVAL_SCOPE_CHANGED: ToolRouting.SHOW,
        GatewayCode.APPROVAL_CONSUMED: ToolRouting.SHOW,
        GatewayCode.APPROVAL_REJECTED: ToolRouting.SHOW,
        GatewayCode.TOOL_TIMEOUT: ToolRouting.SHOW,
        GatewayCode.TOOL_FAILED: ToolRouting.SHOW,
        GatewayCode.ASSIGNMENT_DEPTH_LIMIT: ToolRouting.SHOW,
        GatewayCode.OUTSTANDING_ASSIGNMENTS_LIMIT: ToolRouting.SHOW,
        GatewayCode.CHILDREN_LIMIT: ToolRouting.SHOW,
    }
)
STOPPING: Final = frozenset(code for code, route in ROUTING.items() if route is ToolRouting.STOP)
REPAIRABLE: Final = frozenset(
    code for code, route in ROUTING.items() if route is ToolRouting.REPAIR
)

# The stop once a repairable code finds the root's single repair spent. Each such code is stored
# with its repairable code after the prefix, as `repair_limit` builds it, and fails the run.
REPAIR_LIMIT_PREFIX: Final = "repair_limit:"


def repair_limit(code: str) -> str:
    """The stored stop for a repairable code whose repair is spent, such as
    `repair_limit:plan_out_of_scope`."""
    return f"{REPAIR_LIMIT_PREFIX}{code}"


_BY_VALUE: Final[Mapping[str, Disposition]] = MappingProxyType(
    {code.value: disposition for code, disposition in DISPOSITION.items()}
)


def disposition_of(code: str | None) -> Disposition | None:
    """VERIFY when nothing stopped the pass, the table's disposition for a known code, and None for
    a code missing from it, which its caller suspends as UNMAPPED and logs (Decision 0028 E3)."""
    if code is None:
        return Disposition.VERIFY
    known = _BY_VALUE.get(code)
    if known is not None:
        return known
    if (
        code.startswith(REPAIR_LIMIT_PREFIX)
        and code.removeprefix(REPAIR_LIMIT_PREFIX) in REPAIRABLE
    ):
        return Disposition.FAIL
    return None


# A tool result that suspends the run: the call runs again on resume, any effect from its receipt.
RETRY_LATER: Final = frozenset(
    code for code in GatewayCode if disposition_of(code) is Disposition.SUSPEND
)
# Not a workflow node's own failure: the run is released or suspended, and the node runs again on
# resume, any recorded effect coming back from its receipt. A code that fails the run fails the
# node instead.
STOPS: Final = (
    frozenset(code for code in GatewayCode if disposition_of(code) is Disposition.RELEASE)
    | RETRY_LATER
)


class PassOutcome(_Code):
    """What a pass reports beside its code, whatever the model said at the end."""

    # Every task is done, so verification decides.
    CANDIDATE = "candidate"
    # A person's approval, or a cancelled run's children, has to come first.
    WAITING = "waiting"
    # Not this worker's run any more.
    LOST = "lost"
    # Suspended or failed.
    STOPPED = "stopped"
    # Verified.
    SUCCEEDED = "succeeded"
