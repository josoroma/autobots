"""The `propose_improvement` tool: a run proposes a memory or skill change for a person to review,
and nothing changes yet (PRD 8.5). Tool definitions sit apart from the services they call, so the
registry composes them without the services depending on it (Decision 0029 F12, PPRD-15).
"""

from autobots.application.improvements import propose
from autobots.application.tool_definitions import ToolContext, ToolDefinition, ToolFailed
from autobots.contracts.improvements import ImprovementProposal, ProposalAccepted
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import OperationClass


async def _propose_tool(arguments: ImprovementProposal, context: ToolContext) -> ProposalAccepted:
    candidate_id = await propose(
        context.connection,
        context.scope.workspace_id,
        arguments,
        {"kind": "run", "run_id": str(context.scope.run_id)},
    )
    if candidate_id is None:
        raise ToolFailed("proposal_failed")
    return ProposalAccepted(candidate_id=str(candidate_id), status="proposed")


PROPOSE_IMPROVEMENT = ToolDefinition(
    tool_id="propose_improvement",
    title="Propose improvement",
    group=ToolGroup.LEARNING,
    public_input_fields=("kind", "key"),
    public_output_fields=("candidate_id", "status"),
    version=1,
    description="Propose a memory or skill change for a person to review. It changes nothing yet.",
    input_model=ImprovementProposal,
    output_model=ProposalAccepted,
    operation_class=OperationClass.REVERSIBLE_INTERNAL_WRITE,
    handler=_propose_tool,
)
