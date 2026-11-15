"""The grant, run and tool-version tables are read-only, as domain/models.py's are, so no importer
can widen what a run may call or how it may move (refactor plan R-61, PDOM-20)."""

from collections.abc import Mapping
from typing import Any

import pytest

from autobots.domain import execution, runs, tools

TABLES: dict[str, Mapping[Any, Any]] = {
    "PLAN_TOOLS": tools.PLAN_TOOLS,
    "GENERAL_TOOLS": tools.GENERAL_TOOLS,
    "PROVIDER_TOOLS": tools.PROVIDER_TOOLS,
    "EXPERT_TOOLS": tools.EXPERT_TOOLS,
    "LOOP_TOOL_GRANTS": tools.LOOP_TOOL_GRANTS,
    "WORKFLOW_TOOLS": tools.WORKFLOW_TOOLS,
    "NORMAL_EXITS": runs.NORMAL_EXITS,
    "ACTORS": runs.ACTORS,
    "TARGETS": runs.TARGETS,
    "COMMAND_SOURCES": runs.COMMAND_SOURCES,
    "TOOL_VERSIONS": execution.TOOL_VERSIONS,
}


@pytest.mark.parametrize("name", sorted(TABLES))
def test_a_table_refuses_a_change(name: str) -> None:
    table = TABLES[name]
    key = next(iter(table))
    with pytest.raises(TypeError):
        table[key] = table[key]  # type: ignore[index]  # the write a read-only table refuses
    with pytest.raises(AttributeError):
        table.pop(key)  # type: ignore[attr-defined]  # a read-only mapping has no pop


def test_the_grant_tables_still_compose() -> None:
    assert dict(tools.LOOP_TOOL_GRANTS) == {**tools.PLAN_TOOLS, **tools.GENERAL_TOOLS}
    assert set(tools.GENERAL_TOOLS) <= set(tools.EXPERT_TOOLS)
    assert set(tools.PROVIDER_TOOLS) <= set(tools.EXPERT_TOOLS)
    assert tools.WORKFLOW_TOOLS[tools.DELEGATION_TOOL] == 1
