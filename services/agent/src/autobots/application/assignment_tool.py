"""The `assign_specialist` tool: a coordinator gives a bounded task to an Expert in its session and
waits for its result (PRD 8.2). Tool definitions sit apart from the services they call, so the
registry composes them without the services depending on it (Decision 0029 F12, PPRD-15).
"""

from autobots.application.assignments import Delegation, run_assignment
from autobots.application.run_usage import RootLimits
from autobots.application.tool_definitions import ToolContext, ToolDefinition
from autobots.contracts.assignments import AssignmentResult, AssignSpecialist
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import DELEGATION_TOOL, OperationClass


def assign_tool(delegation: Delegation | None) -> ToolDefinition:
    """With no delegation, as the catalog describes it, a call refuses before any assignment or
    child exists (XMOD-01)."""

    async def run(arguments: AssignSpecialist, context: ToolContext) -> AssignmentResult:
        return await run_assignment(delegation, arguments, context)

    return ToolDefinition(
        tool_id=DELEGATION_TOOL,
        title="Assign specialist",
        group=ToolGroup.DELEGATION,
        public_input_fields=("expert_id",),
        public_output_fields=("assignment_id", "child_run_id", "outcome", "code"),
        version=1,
        description="Give a bounded task to an Expert in this session, and wait for its result.",
        input_model=AssignSpecialist,
        output_model=AssignmentResult,
        operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
        handler=run,
        timeout_seconds=(delegation.limits if delegation else RootLimits()).active_seconds,
        safe_to_repeat=True,
    )
