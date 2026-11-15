"""The one index of tools: every definition a goal's pass, a workflow or the catalog is built with,
so the catalog lists exactly what the worker runs (PRD-Tool-Catalog TC-01, XMOD-01, PTOL-08).

This is the composition edge. It may import every tool module, in application/ and adapters/, and
nothing in application/ imports it: api/app.py and operations/worker.py take what it builds and pass
it in, the catalog to the routes, admission, Experts and routines, and `build_registry` to each
pass through `LoopConfig.tool_set`. A run's scope, never this index, decides what it may
call (SP-013).
"""

from collections.abc import Mapping

from autobots.adapters.github_issues import GITHUB_ISSUE, GITHUB_ISSUE_V2
from autobots.adapters.github_pulls import GITHUB_PULL_REQUEST
from autobots.adapters.github_reads import GITHUB_READ_TOOLS
from autobots.adapters.jina import JINA_TOOLS
from autobots.adapters.market_data import MARKET_TOOLS
from autobots.adapters.remote_files import STORE_REMOTE_FILE
from autobots.adapters.tavily import TAVILY_TOOLS
from autobots.application import browsing_tool
from autobots.application.artifacts import publish_tool
from autobots.application.assignments import assign_tool
from autobots.application.code_tools import CODE_TOOLS
from autobots.application.cronjob_tool import cronjob_tool
from autobots.application.improvements import PROPOSE_IMPROVEMENT
from autobots.application.memory import READ_OFFLOAD, SEARCH_MEMORY
from autobots.application.plans import plan_tools
from autobots.application.tool_catalog import Catalog
from autobots.application.tool_definitions import (
    Browsing,
    ToolDefinition,
    ToolRegistry,
    ToolRuntime,
)
from autobots.application.tools import (
    CALCULATE,
    READ_CSV,
    READ_RUN_FILE,
    READ_RUN_FILE_V2,
    SAVE_ARTIFACT,
)
from autobots.application.workflow_runner import APPROVAL_GATE


def tool_definitions(
    runtime: ToolRuntime | None, *, workflow: bool = False, browsing: Browsing | None = None
) -> tuple[ToolDefinition, ...]:
    """Every tool, bound to `runtime` (`_bound`). A workflow adds its approval step, and
    `browse_goal` is here only when `browsing` is passed (AB-02, Decision 0025 V6).

    The module's names are read at each call, so a qualification worker can swap one definition for
    a recording fake (tests/qualification/worker.py)."""
    return (
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
        cronjob_tool(CATALOG),
        *_bound(runtime),
        *((APPROVAL_GATE,) if workflow else ()),
        *((browsing_tool.browse_tool(browsing.runtime, browsing.qualified),) if browsing else ()),
    )


def _bound(runtime: ToolRuntime | None) -> tuple[ToolDefinition, ...]:
    """The definitions a pass's runtime binds. With no runtime, as the catalog builds them, each
    still describes itself and its handler refuses before any effect. A pass registers
    `publish_artifact` only with an object store and `assign_specialist` only with a way to drive
    its children, so its model is never shown a tool it can't use (SP-013)."""
    if runtime is None:
        return (*plan_tools(None), publish_tool(None), assign_tool(None))
    store, delegation = runtime.object_store, runtime.delegation
    return (
        *plan_tools(runtime.limits),
        *((publish_tool(store),) if store is not None else ()),
        *((assign_tool(delegation),) if delegation is not None else ()),
    )


def build_registry(
    runtime: ToolRuntime | None, *, workflow: bool = False, browsing: Browsing | None = None
) -> ToolRegistry:
    """The registry of `tool_definitions`. It is the worker's `LoopConfig.tool_set`
    (application.tool_definitions.ToolSet)."""
    registry = ToolRegistry()
    for tool in tool_definitions(runtime, workflow=workflow, browsing=browsing):
        registry.register(tool)
    return registry


def catalog_registry(environ: Mapping[str, str] | None = None) -> ToolRegistry:
    """Every tool any run can be granted, as a worker builds it for a workflow with this
    workspace's Keys & vars view, without its resources (TC-01). `browse_goal` is registered only
    while that view switches browsing on and its executor is qualified (AB-02, Decision 0025 V6).
    Without a view, the process environment decides."""

    def qualified() -> bool:
        return browsing_tool.executor_ready(environ=environ)

    return build_registry(
        None, workflow=True, browsing=Browsing(qualified) if qualified() else None
    )


# The catalog over `catalog_registry`, one per process. The `cronjob` tool admits through it, and
# `catalog()` hands it to the API, the worker and the checks.
CATALOG = Catalog(catalog_registry)


def catalog() -> Catalog:
    """This process's catalog over the registry the worker runs (TC-01)."""
    return CATALOG
