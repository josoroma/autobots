"""Retired tools: no shipped map or registry holds one, a revision drops one, and a run that
recorded one continues (Decision 0036 R2, R4 and R5, US-18.1)."""

from collections.abc import Mapping

import pytest

from autobots.adapters.tool_registry import catalog, tool_definitions
from autobots.application.experts import ExpertRefused, drop_retired, expand_groups, validate_config
from autobots.application.tool_definitions import Browsing
from autobots.contracts.experts import ExpertConfig
from autobots.domain.execution import GRAPH_STATE_VERSION, TOOL_VERSIONS, incompatibility
from autobots.domain.tools import (
    EXPERT_TOOLS,
    GENERAL_TOOLS,
    LOOP_TOOL_GRANTS,
    PLAN_TOOLS,
    PROVIDER_TOOLS,
    RETIRED_TOOLS,
    WORKFLOW_TOOLS,
    retired_in,
    without_retired,
)

CATALOG = catalog()


def test_inflation_rates_is_retired() -> None:
    assert "inflation_rates" in RETIRED_TOOLS


def test_the_check_names_a_retired_tool_a_map_holds() -> None:
    assert retired_in({"market_history": 1, "inflation_rates": 1}) == ["inflation_rates"]
    assert retired_in(["calculate", "market_history"]) == []


@pytest.mark.parametrize(
    ("name", "tools"),
    [
        ("PLAN_TOOLS", PLAN_TOOLS),
        ("GENERAL_TOOLS", GENERAL_TOOLS),
        ("PROVIDER_TOOLS", PROVIDER_TOOLS),
        ("EXPERT_TOOLS", EXPERT_TOOLS),
        ("LOOP_TOOL_GRANTS", LOOP_TOOL_GRANTS),
        ("WORKFLOW_TOOLS", WORKFLOW_TOOLS),
        ("TOOL_VERSIONS", TOOL_VERSIONS),
    ],
)
def test_no_shipped_grant_map_holds_a_retired_tool(name: str, tools: Mapping[str, int]) -> None:
    assert retired_in(tools) == [], name


def test_the_registry_holds_no_retired_tool() -> None:
    every = tool_definitions(None, workflow=True, browsing=Browsing(lambda: True))
    registered = [tool.tool_id for tool in every]
    assert retired_in(registered) == []
    assert retired_in(item.tool_id for item in CATALOG.descriptors({})) == []


def test_without_retired_keeps_the_order_of_the_rest() -> None:
    assert without_retired(["read_csv", "inflation_rates", "market_history"]) == [
        "read_csv",
        "market_history",
    ]


def test_a_revision_drops_a_retired_tool_before_it_is_checked() -> None:
    config = ExpertConfig(tools=["inflation_rates", "market_history"])
    saved = expand_groups(drop_retired(config), CATALOG, {})
    validate_config(saved, CATALOG, {})
    assert saved.tools == ["market_history"]


def test_a_revision_without_a_retired_tool_is_the_same_config() -> None:
    config = ExpertConfig(tools=["market_history"])
    assert drop_retired(config) is config


def test_a_tool_that_never_existed_is_still_refused() -> None:
    config = ExpertConfig(tools=["inflation_rate", "market_history"])
    with pytest.raises(ExpertRefused) as refused:
        validate_config(expand_groups(drop_retired(config), CATALOG, {}), CATALOG, {})
    assert refused.value.code == "expert_tool_not_available"


def test_a_run_that_recorded_a_retired_tool_can_continue() -> None:
    recorded = {
        "graph_state": GRAPH_STATE_VERSION,
        "tools": {**TOOL_VERSIONS, "inflation_rates": 1},
    }
    assert "inflation_rates" not in TOOL_VERSIONS
    assert incompatibility(recorded) is None


def test_a_removed_tool_that_is_not_retired_still_stops_a_run() -> None:
    recorded = {
        "graph_state": GRAPH_STATE_VERSION,
        "tools": {**TOOL_VERSIONS, "inflation_rates": 1, "old_tool": 1},
    }
    assert incompatibility(recorded) == "old_tool v1 no longer exists"
