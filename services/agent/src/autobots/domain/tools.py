"""The tool vocabulary and its resource rule, SP-013 and PRD 9.1.

The grant tables are read-only, as domain/models.py's are: they decide what a run may call, so no
importer can widen them (PDOM-20).
"""

from collections.abc import Collection, Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final


class OperationClass(StrEnum):
    PURE = "pure"
    READ_ONLY = "read_only"
    REVERSIBLE_INTERNAL_WRITE = "reversible_internal_write"
    CONSEQUENTIAL_EXTERNAL_WRITE = "consequential_external_write"
    ARBITRARY_EXECUTION = "arbitrary_execution"


# The plan tools come with any loop. An Expert chooses among the rest. General tools can't reach
# the host or the network; provider tools reach only their provider, through the URL guard.
PLAN_TOOLS: Final[Mapping[str, int]] = MappingProxyType(
    {"propose_plan": 1, "complete_task": 1, "read_offload": 1}
)
GENERAL_TOOLS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "calculate": 1,
        # Version 2 for new grants. Runs that pinned version 1 keep it, and it stays registered.
        "read_run_file": 2,
        "read_csv": 1,
        "save_artifact": 1,
        "publish_artifact": 1,
        "search_memory": 1,
    }
)
# Tool-provider tools, Decision 0017. Each needs its provider's key, read per attempt.
PROVIDER_TOOLS: Final[Mapping[str, int]] = MappingProxyType(
    {
        # Version 2 of each search tool pages its results (Decision 0031). A run or Expert version
        # that pinned version 1 keeps it, and it stays registered.
        "tavily_search": 2,
        "tavily_extract": 1,
        "tavily_map": 1,
        "tavily_crawl": 1,
        "search_web": 2,
        "extract_website_content": 1,
        # Google through SerpApi (Decisions 0032 and 0033). google_extract needs no key, so it is
        # granted beside the provider tools.
        "google_search": 1,
        "google_map": 1,
        "google_crawl": 1,
        "market_history": 1,
    }
)
EXPERT_TOOLS: Final[Mapping[str, int]] = MappingProxyType(
    {
        **GENERAL_TOOLS,
        # Proposing an improvement changes nothing by itself, but a run gets it only if an owner
        # chose that.
        "propose_improvement": 1,
        # Version 2 adds labels (PRD-Studio GH-05). A run whose grants pinned version 1 keeps it.
        "create_github_issue": 2,
        # Read only, on the one configured repository (PRD-Studio GH-01 to GH-04).
        "github_list_pull_requests": 1,
        "github_list_workflow_runs": 1,
        "github_search_issues": 1,
        "github_read_file": 1,
        # Consequential, with approval on every call and each file's diff (PRD-Studio GH-06).
        "github_open_pull_request": 1,
        # It reaches the network, so only an owner's Expert grants it, never a plain goal.
        "store_remote_file": 1,
        # Reads pages directly from their sites, in the Google toolkit (Decision 0033 K3).
        "google_extract": 1,
        # Reads a published artifact of the workspace, so a workflow step reads an earlier one's
        # work. Only an Expert grants it, never a plain goal (Decision 0034 A3).
        "read_artifact": 1,
        # Code tools over the run's own files, for Experts that do code-shaped work (Decision 0017).
        "search_files": 1,
        "read_code_file": 1,
        "write_code_file": 1,
        "patch_code_file": 1,
        **PROVIDER_TOOLS,
        # Arbitrary execution in the isolated browser, only while it's qualified (US-14.12), with
        # browser-use's limits from version 2 (Decision 0035 Y9) and typed results, submits and
        # bot_check from version 3 (Y10 to Y12).
        "browse_goal": 3,
        # Manages the workspace's routines, every action but `list` approved (Decision 0026).
        "cronjob": 1,
    }
)
LOOP_TOOL_GRANTS: Final[Mapping[str, int]] = MappingProxyType({**PLAN_TOOLS, **GENERAL_TOOLS})
# Only a coordinator session's runs get this, and an Expert's own configuration can't name it.
DELEGATION_TOOL = "assign_specialist"
# The tools a workflow's own blocks call by name (application/workflow_runner.py TOOL_BLOCKS).
READ_RUN_FILE_TOOL = "read_run_file"
SAVE_ARTIFACT_TOOL = "save_artifact"
PUBLISH_ARTIFACT_TOOL = "publish_artifact"
READ_ARTIFACT_TOOL = "read_artifact"
WORKFLOW_APPROVAL_TOOL = "workflow_approval"
# What a workflow's own blocks reach. Its approval step is the only consequential one here.
WORKFLOW_TOOLS: Final[Mapping[str, int]] = MappingProxyType(
    {**LOOP_TOOL_GRANTS, DELEGATION_TOOL: 1, WORKFLOW_APPROVAL_TOOL: 1}
)

# Tools Autobots has removed. A saved Expert version, routine or run may still name one: a grant
# leaves it out, a revision drops it, and a run that recorded it continues without it. A retired
# name is never reused for another tool (Decision 0036 R2 to R5).
RETIRED_TOOLS: Final[frozenset[str]] = frozenset({"inflation_rates"})


def without_retired(tools: Iterable[str]) -> list[str]:
    """The names in their order, less the retired ones (Decision 0036 R3 and R4)."""
    return [tool for tool in tools if tool not in RETIRED_TOOLS]


def retired_in(tools: Iterable[str]) -> list[str]:
    """The retired names among `tools`, which no shipped grant map or registry holds (R2)."""
    return sorted({tool for tool in tools if tool in RETIRED_TOOLS})


def workflow_grant(
    requested: Collection[str] | None, agents: Mapping[str, int] | None = None
) -> Mapping[str, int]:
    """What a workflow execution's run may call: every workflow tool, or only the requested ones,
    always with the plan tools and the approval step, in WORKFLOW_TOOLS' order (PRD 7.3).

    `agents` are the tools of the Experts its agent steps name. They're granted too, so each step's
    child gets its Expert's tools, which the child's grant intersects with this one (Decision 0034
    F3). The workflow's own blocks never call them. A requested list narrows them as well."""
    base = (
        WORKFLOW_TOOLS
        if requested is None
        else {
            tool: version
            for tool, version in WORKFLOW_TOOLS.items()
            if tool in requested or tool in PLAN_TOOLS or tool == WORKFLOW_APPROVAL_TOOL
        }
    )
    extra = {
        tool: version
        for tool, version in (agents or {}).items()
        if tool not in base and (requested is None or tool in requested)
    }
    return {**base, **extra} if extra else base


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
