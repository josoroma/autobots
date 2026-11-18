"""US-14.24: tool switches' rules and their effect on the catalog, Decision 0033 W1, W2 and W5. The
database, the gateway and the routes are checked on a disposable stack (tests/db/checks)."""

from autobots.adapters.tool_registry import catalog
from autobots.application.tool_keys import KeySources
from autobots.contracts.tool_catalog import ToolSwitchView
from autobots.domain.tool_switches import (
    GROUP_TURNED_OFF,
    TURNED_OFF,
    Switch,
    Switches,
    switchable_tool,
    turned_off_by,
)
from autobots.domain.tools import EXPERT_TOOLS

GOOGLE = ("google_search", "google_map", "google_extract", "google_crawl")


def view(switches: Switches) -> KeySources:
    found = KeySources({"SERPAPI_API_KEY": "<settings>"})
    found.sources = {"SERPAPI_API_KEY": "settings"}
    found.switches = switches
    return found


def describe(switches: Switches) -> dict[str, tuple[str, str | None, ToolSwitchView]]:
    """Each registered switchable tool's availability, reason and switch."""
    return {
        item.tool_id: (item.availability, item.availability_reason, item.switch)
        for item in catalog().catalog(view(switches)).tools
        if item.switch is not None
    }


def test_only_expert_grantable_tools_are_switchable() -> None:
    assert all(switchable_tool(tool_id) for tool_id in EXPERT_TOOLS)
    for tool_id in ("propose_plan", "complete_task", "read_offload", "assign_specialist"):
        assert not switchable_tool(tool_id)
        assert turned_off_by(tool_id, "planning", {("group", "planning"): Switch(False, 1)}) is None


def test_everything_starts_on_at_version_0() -> None:
    found = catalog().catalog(view({}))
    for item in found.tools:
        # A planned tool, such as browse_goal before its executor qualifies, isn't registered, so
        # it has no switch until it is.
        if switchable_tool(item.tool_id) and item.registered:
            assert item.switch is not None
            assert (item.switch.enabled, item.switch.version, item.switch.by) == (True, 0, None)
        else:
            assert item.switch is None
    holds = {
        group.group: any(
            switchable_tool(tool_id)
            and any(t.tool_id == tool_id and t.registered for t in found.tools)
            for tool_id in group.tool_ids
        )
        for group in found.groups
    }
    for group in found.groups:
        if holds[group.group]:
            assert group.switch is not None, group.group
            assert (group.switch.enabled, group.switch.version) == (True, 0), group.group
        else:
            assert group.switch is None, group.group
    assert not holds["planning"] and not holds.get("delegation", False)
    google = next(group for group in found.groups if group.group == "google")
    assert google.switch is not None and (google.switch.enabled, google.switch.version) == (True, 0)
    planning = next(group for group in found.groups if group.group == "planning")
    assert planning.switch is None
    assert found.viewer_can_switch is False


def test_a_tool_turned_off_is_disabled_by_policy_with_its_reason() -> None:
    found = describe({("tool", "google_crawl"): Switch(False, 1)})
    availability, why, switch = found["google_crawl"]
    assert (availability, why) == ("disabled_by_policy", TURNED_OFF)
    assert switch is not None and (switch.enabled, switch.version, switch.by) == (False, 1, "tool")
    assert found["google_search"][0] == "available"
    assert catalog().unavailable(
        ["google_crawl", "google_search"], view({("tool", "google_crawl"): Switch(False, 1)})
    ) == ["google_crawl"]


def test_a_group_turned_off_turns_off_its_tools_whatever_their_own_switches() -> None:
    switches: Switches = {
        ("group", "google"): Switch(False, 1),
        ("tool", "google_search"): Switch(True, 2),
    }
    found = describe(switches)
    for tool_id in GOOGLE:
        availability, why, switch = found[tool_id]
        assert (availability, why) == ("disabled_by_policy", GROUP_TURNED_OFF), tool_id
        assert switch.by == "group"
    assert found["google_search"][2].enabled is True
    assert found["search_web"][0] != "disabled_by_policy"
    back_on = describe(
        {("group", "google"): Switch(True, 2), ("tool", "google_search"): Switch(True, 2)}
    )
    assert all(back_on[tool_id][0] == "available" for tool_id in GOOGLE)


def test_a_plain_environment_has_every_tool_on() -> None:
    assert all(
        item.switch is None or item.switch.by is None for item in catalog().catalog({}).tools
    )
