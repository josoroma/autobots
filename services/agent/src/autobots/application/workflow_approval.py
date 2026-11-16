"""The `workflow_approval` tool: a workflow's explicit approval step, which policy holds for a
person before the step's value passes on (PRD 7.3). Passing through it is the gate itself, and
replay finds the decision by operation identity. Tool definitions sit apart from the services they
call, so the registry composes them without the services depending on it (Decision 0029 F12,
PPRD-15).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict

from autobots.application.tool_definitions import ApprovalPolicy, ToolContext, ToolDefinition
from autobots.domain.tool_catalog import ToolGroup
from autobots.domain.tools import WORKFLOW_APPROVAL_TOOL, OperationClass


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node: str
    value: Any = None


class ApprovalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: Any = None


async def _release(arguments: ApprovalInput, _: ToolContext) -> ApprovalOutput:
    return ApprovalOutput(value=arguments.value)


APPROVAL_GATE = ToolDefinition(
    tool_id=WORKFLOW_APPROVAL_TOOL,
    title="Workflow approval",
    group=ToolGroup.PLANNING,
    public_input_fields=("node",),
    public_output_fields=(),
    version=1,
    description="A workflow's explicit approval step.",
    input_model=ApprovalInput,
    output_model=ApprovalOutput,
    operation_class=OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE,
    handler=_release,
    approval=ApprovalPolicy(
        reason="This workflow has an approval step, so policy holds it for a person."
    ),
)
