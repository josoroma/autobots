"""The tool vocabulary and its resource rule, SP-013 and PRD 9.1."""

from enum import StrEnum


class OperationClass(StrEnum):
    PURE = "pure"
    READ_ONLY = "read_only"
    REVERSIBLE_INTERNAL_WRITE = "reversible_internal_write"
    CONSEQUENTIAL_EXTERNAL_WRITE = "consequential_external_write"
    ARBITRARY_EXECUTION = "arbitrary_execution"


# The plan tools come with any loop. An Expert chooses among the rest, and nothing here can reach
# the host or the network.
PLAN_TOOLS = {"propose_plan": 1, "complete_task": 1}
EXPERT_TOOLS = {"calculate": 1, "read_run_file": 1, "save_artifact": 1, "publish_artifact": 1}
LOOP_TOOL_GRANTS = {**PLAN_TOOLS, **EXPERT_TOOLS}
# Only a coordinator session's runs get this, and an Expert's own configuration can't name it.
DELEGATION_TOOL = "assign_specialist"
RUN_FILE_GRANTS = ("inputs", "outputs")

# Only these leave an effect, so only these get an operation identity and a receipt.
EFFECTFUL = frozenset(
    {OperationClass.REVERSIBLE_INTERNAL_WRITE, OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE}
)


class ToolOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    DENIED = "denied"


def path_granted(path: str, grants: tuple[str, ...]) -> bool:
    """First-class deny: anything not plainly inside an explicit grant is outside it."""
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return False
    return any(path == grant or path.startswith(grant.rstrip("/") + "/") for grant in grants)
