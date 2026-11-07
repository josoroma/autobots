"""The catalog's pure vocabulary, PRD-Tool-Catalog TC-02 to TC-04 and Decision 0017."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from autobots.domain.tools import (
    DELEGATION_TOOL,
    EXPERT_TOOLS,
    LOOP_TOOL_GRANTS,
    OperationClass,
)


class ToolGroup(StrEnum):
    PLANNING = "planning"
    GENERAL = "general"
    WEB_SEARCH = "web_search"
    WEB_EXTRACTION = "web_extraction"
    WEB_CRAWLING = "web_crawling"
    FILES = "files"
    MARKET_DATA = "market_data"
    BROWSING = "browsing"
    CODE = "code"
    CONNECTORS = "connectors"
    DELEGATION = "delegation"
    LEARNING = "learning"


GROUP_TITLES: Mapping[ToolGroup, tuple[str, str]] = {
    ToolGroup.PLANNING: ("Planning", "Propose a plan and record finished tasks."),
    ToolGroup.GENERAL: ("General", "Arithmetic, memory and saving files inside the run."),
    ToolGroup.WEB_SEARCH: ("Web search", "Search the web through a tool provider."),
    ToolGroup.WEB_EXTRACTION: ("Website extraction", "Read web pages as markdown."),
    ToolGroup.WEB_CRAWLING: ("Web crawling", "Map or crawl a site within fixed ceilings."),
    ToolGroup.FILES: ("Files", "Read, parse and store the run's own files."),
    ToolGroup.MARKET_DATA: ("Market data", "Prices, exchange rates and inflation."),
    ToolGroup.BROWSING: ("Autonomous browsing", "Goal-driven browser control."),
    ToolGroup.CODE: ("Code", "Search and edit the run's own files as code."),
    ToolGroup.CONNECTORS: ("Connectors", "Effects in an outside service, each approved."),
    ToolGroup.DELEGATION: ("Delegation", "Assign bounded work to an Expert."),
    ToolGroup.LEARNING: ("Learning", "Propose memory or skill changes for review."),
}


class ToolProvider(StrEnum):
    AUTOBOTS = "autobots"
    TAVILY = "tavily"
    JINA = "jina"
    YAHOO_FINANCE = "yahoo_finance"
    WORLD_BANK = "world_bank"
    GITHUB = "github"


class CostClass(StrEnum):
    FREE_LOCAL = "free_local"
    METERED_PROVIDER = "metered_provider"


class SideEffect(StrEnum):
    NONE = "none"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    ARBITRARY = "arbitrary"


SIDE_EFFECTS: Mapping[OperationClass, SideEffect] = {
    OperationClass.PURE: SideEffect.NONE,
    OperationClass.READ_ONLY: SideEffect.NONE,
    OperationClass.REVERSIBLE_INTERNAL_WRITE: SideEffect.INTERNAL_WRITE,
    OperationClass.CONSEQUENTIAL_EXTERNAL_WRITE: SideEffect.EXTERNAL_WRITE,
    OperationClass.ARBITRARY_EXECUTION: SideEffect.ARBITRARY,
}


class ToolAvailability(StrEnum):
    AVAILABLE = "available"
    KEY_MISSING = "key_missing"
    DISABLED_BY_POLICY = "disabled_by_policy"
    NOT_QUALIFIED = "not_qualified"


class GrantSite(StrEnum):
    GOAL = "goal"
    EXPERT = "expert"
    WORKFLOW_NODE = "workflow_node"
    COORDINATOR = "coordinator"


@dataclass(frozen=True)
class KeyRequirement:
    """Names only. A value, prefix, length or hash of a key never appears in the catalog."""

    credential: str
    variables: tuple[str, ...]


def key_availability(
    requirement: KeyRequirement | None, environ: Mapping[str, str]
) -> tuple[ToolAvailability, str | None]:
    if requirement is None:
        return ToolAvailability.AVAILABLE, None
    if all(environ.get(variable, "").strip() for variable in requirement.variables):
        return ToolAvailability.AVAILABLE, None
    return ToolAvailability.KEY_MISSING, f"{requirement.credential}_key_missing"


def grant_sites(tool_id: str, workflow_tools: Mapping[str, int]) -> list[str]:
    """Where a grant may name a tool, read from the same sets that enforce it."""
    sites = []
    if tool_id in LOOP_TOOL_GRANTS:
        sites.append(GrantSite.GOAL.value)
    if tool_id in EXPERT_TOOLS:
        sites.append(GrantSite.EXPERT.value)
    if tool_id in workflow_tools:
        sites.append(GrantSite.WORKFLOW_NODE.value)
    if tool_id == DELEGATION_TOOL:
        sites.append(GrantSite.COORDINATOR.value)
    return sites


@dataclass(frozen=True)
class PlannedTool:
    """Catalogued so a screen can show it, never registered, so nothing can call it."""

    tool_id: str
    version: int
    title: str
    description: str
    group: ToolGroup
    provider: ToolProvider
    operation_class: OperationClass
    reason: str


# Decision 0017 C3 and C4, and Decision 0020 L5. Listed this way only while unqualified.
PLANNED_TOOLS: tuple[PlannedTool, ...] = (
    PlannedTool(
        tool_id="browse_goal",
        version=1,
        title="Goal-driven browsing",
        description="Read websites in an isolated browser to pursue a task. Disabled until the "
        "isolated executor is qualified.",
        group=ToolGroup.BROWSING,
        provider=ToolProvider.AUTOBOTS,
        operation_class=OperationClass.ARBITRARY_EXECUTION,
        reason="isolated_executor_not_qualified",
    ),
)
