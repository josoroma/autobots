"""Tool switches' pure rules, Decision 0033 W1 and W2 and PRD-Tool-Catalog TW-01 and TW-02.

An owner turns an Expert-grantable tool, or a whole group, on or off for the workspace. Everything
starts on. A tool is on only while both its own switch and its group's are. The plan, delegation
and workflow approval tools aren't switchable, so a run can't lose what it needs to plan and
finish.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from autobots.domain.tools import EXPERT_TOOLS

SwitchKind = Literal["tool", "group"]
TURNED_OFF = "turned_off"
GROUP_TURNED_OFF = "group_turned_off"


@dataclass(frozen=True)
class Switch:
    enabled: bool = True
    # 0 until the switch is first changed (no row).
    version: int = 0


ON = Switch()
Switches = Mapping[tuple[SwitchKind, str], Switch]


def switchable_tool(tool_id: str) -> bool:
    return tool_id in EXPERT_TOOLS


def state(switches: Switches, kind: SwitchKind, target: str) -> Switch:
    return switches.get((kind, target), ON)


def turned_off_by(tool_id: str, group: str, switches: Switches) -> SwitchKind | None:
    """Which switch keeps a tool off, or None while it is on. The group's comes first, since it is
    the one to turn back on first."""
    if not switchable_tool(tool_id):
        return None
    if not state(switches, "group", group).enabled:
        return "group"
    if not state(switches, "tool", tool_id).enabled:
        return "tool"
    return None


def reason(by: SwitchKind) -> str:
    return GROUP_TURNED_OFF if by == "group" else TURNED_OFF
