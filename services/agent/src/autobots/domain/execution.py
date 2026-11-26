"""What a saved run depends on, PRD 10.3. A run resumes only under semantics it was admitted with.

Raising a number here means old checkpoints can't continue, unless the change is also listed as
preserving behavior. Listing one is a decision for a review, not a way to keep the queue moving.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Final

from autobots.domain.tools import RETIRED_TOOLS

# The shape of graph state and how the loop reads it.
GRAPH_STATE_VERSION = 1
COMPATIBLE_GRAPH_STATES = frozenset({1})

# Every tool the loop can offer, read-only (PDOM-20). tests/test_execution_contract.py keeps this
# equal to the registry, and tests/test_tool_schema_versions.py keeps each version's published
# schemas as they were, so a changed schema is a new version here (Decision 0029 F13).
TOOL_VERSIONS: Final[Mapping[str, int]] = MappingProxyType(
    {
        "append_to_file": 1,
        "assign_specialist": 1,
        "calculate": 1,
        "complete_task": 1,
        "create_github_issue": 2,
        "cronjob": 1,
        "extract_website_content": 1,
        "github_list_pull_requests": 1,
        "github_list_workflow_runs": 1,
        "github_open_pull_request": 1,
        "github_read_file": 1,
        "github_search_issues": 1,
        "google_crawl": 1,
        "google_extract": 1,
        "google_map": 1,
        "google_search": 1,
        "market_history": 1,
        "patch_code_file": 1,
        "propose_improvement": 1,
        "propose_plan": 1,
        "publish_artifact": 1,
        "read_artifact": 1,
        "read_offload": 1,
        "read_code_file": 1,
        "read_csv": 1,
        "read_run_file": 2,
        "save_artifact": 1,
        "search_files": 1,
        "search_memory": 1,
        "search_web": 2,
        "store_remote_file": 1,
        "tavily_crawl": 1,
        "tavily_extract": 1,
        "tavily_map": 1,
        "tavily_search": 2,
        "write_code_file": 1,
    }
)
# (tool, recorded version, current version), only where old checkpoints keep their meaning.
# read_run_file 1 stays registered, and a run that pinned it keeps calling it (US-14.9).
# create_github_issue 1 stays registered too, unchanged, beside version 2's labels (US-15.14).
# search_web 1 and tavily_search 1 stay registered beside version 2's pages (Decision 0031 S9).
COMPATIBLE_TOOL_CHANGES: frozenset[tuple[str, int, int]] = frozenset(
    {
        ("read_run_file", 1, 2),
        ("create_github_issue", 1, 2),
        ("search_web", 1, 2),
        ("tavily_search", 1, 2),
    }
)

INCOMPATIBLE = "incompatible_version"


def current_contract() -> dict[str, Any]:
    return {"graph_state": GRAPH_STATE_VERSION, "tools": dict(TOOL_VERSIONS)}


def incompatibility(recorded: Mapping[str, Any] | None) -> str | None:
    """Why this run can't continue here, as a detail safe to show, or None."""
    if recorded is None:
        return "no execution contract is recorded"
    if recorded.get("graph_state") not in COMPATIBLE_GRAPH_STATES:
        return f"graph state {recorded.get('graph_state')} isn't readable by this release"
    for tool, version in (recorded.get("tools") or {}).items():
        current = TOOL_VERSIONS.get(tool)
        if current == version:
            continue
        if current is None:
            # A retired tool stops nothing: the run's model no longer sees it, and a call to it is
            # refused as tool_not_registered (Decision 0036 R5).
            if tool in RETIRED_TOOLS:
                continue
            return f"{tool} v{version} no longer exists"
        if (tool, version, current) not in COMPATIBLE_TOOL_CHANGES:
            return f"{tool} changed from v{version} to v{current}"
    return None
