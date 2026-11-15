"""The tools every pass is built with: the goal loop's agent, a workflow's steps and the catalog
(PRD-Tool-Catalog TC-01). A run's scope, never this registry, decides what it may call (SP-013)."""

from typing import cast

from autobots.adapters.github_issues import GITHUB_ISSUE, GITHUB_ISSUE_V2
from autobots.adapters.github_pulls import GITHUB_PULL_REQUEST
from autobots.adapters.github_reads import GITHUB_READ_TOOLS
from autobots.adapters.jina import JINA_TOOLS
from autobots.adapters.market_data import MARKET_TOOLS
from autobots.adapters.remote_files import STORE_REMOTE_FILE
from autobots.adapters.tavily import TAVILY_TOOLS
from autobots.application.artifacts import ObjectStore, publish_tool
from autobots.application.assignments import Delegation, assign_tool
from autobots.application.code_tools import CODE_TOOLS
from autobots.application.cronjob_tool import CRONJOB
from autobots.application.improvements import PROPOSE_IMPROVEMENT
from autobots.application.memory import READ_OFFLOAD, SEARCH_MEMORY
from autobots.application.plans import plan_tools
from autobots.application.run_usage import RootLimits
from autobots.application.tool_gateway import ToolDefinition, ToolRegistry
from autobots.application.tools import (
    CALCULATE,
    READ_CSV,
    READ_RUN_FILE,
    READ_RUN_FILE_V2,
    SAVE_ARTIFACT,
)


def loop_registry(
    limits: RootLimits,
    object_store: object = None,
    delegation: Delegation | None = None,
    extra: tuple[ToolDefinition, ...] = (),
) -> ToolRegistry:
    registry = ToolRegistry()
    tools = (
        CALCULATE,
        READ_RUN_FILE,
        READ_RUN_FILE_V2,
        READ_CSV,
        SAVE_ARTIFACT,
        STORE_REMOTE_FILE,
        SEARCH_MEMORY,
        READ_OFFLOAD,
        PROPOSE_IMPROVEMENT,
        GITHUB_ISSUE,
        GITHUB_ISSUE_V2,
        *GITHUB_READ_TOOLS,
        GITHUB_PULL_REQUEST,
        *TAVILY_TOOLS,
        *JINA_TOOLS,
        *MARKET_TOOLS,
        *CODE_TOOLS,
        CRONJOB,
    )
    for tool in (*tools, *plan_tools(limits)):
        registry.register(tool)
    if object_store is not None:
        # A run passes its store. The catalog passes a placeholder, as it only describes the tool.
        registry.register(publish_tool(cast(ObjectStore, object_store)))
    if delegation is not None:
        registry.register(assign_tool(delegation))
    for tool in extra:
        registry.register(tool)
    return registry
