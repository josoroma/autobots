"""US-14.20, Decision 0026 G1 and TG-01: every tool says what it does, when to use it and why."""

from dataclasses import replace

import pytest

from autobots.adapters.tool_registry import catalog, catalog_registry
from autobots.application.tool_catalog import MissingGuide, all_descriptors, require_guides
from autobots.application.tool_definitions import ToolRegistry
from autobots.domain import tool_guides
from autobots.domain.tool_guides import TOOL_GUIDES, ToolGuide

CATALOG = catalog()


def test_every_registered_and_planned_tool_has_a_full_guide() -> None:
    described = CATALOG.descriptors({})
    assert described
    require_guides(item.tool_id for item in described)
    for item in described:
        assert item.guide.what.strip() and item.guide.when.strip() and item.guide.why.strip(), item
    registered = {tool.tool_id for tool in catalog_registry().definitions()}
    assert registered <= set(TOOL_GUIDES)
    # Every guide belongs to a tool someone can see, so none is left behind by a removal.
    assert set(TOOL_GUIDES) == {item.tool_id for item in described} | registered


def test_the_catalog_and_each_version_carry_the_guide() -> None:
    catalog = CATALOG.catalog({})
    calculate = next(item for item in catalog.tools if item.tool_id == "calculate")
    assert calculate.guide.what.startswith("Computes the sum")
    assert set(calculate.guide.model_dump()) == {"what", "when", "why"}


@pytest.mark.parametrize(
    "guide", [None, ToolGuide("", "When.", "Why."), ToolGuide("What.", " ", "Why.")]
)
def test_a_tool_without_a_full_guide_fails_naming_it(
    guide: ToolGuide | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calculate = next(
        tool for tool in catalog_registry().definitions() if tool.tool_id == "calculate"
    )
    stray = replace(calculate, tool_id="unguided_tool")
    registry = ToolRegistry()
    registry.register(stray)
    guides = dict(TOOL_GUIDES)
    if guide is not None:
        guides["unguided_tool"] = guide
    monkeypatch.setattr(tool_guides, "TOOL_GUIDES", guides)
    monkeypatch.setattr("autobots.application.tool_catalog.TOOL_GUIDES", guides)
    with pytest.raises(MissingGuide, match="unguided_tool"):
        require_guides(item.tool_id for item in all_descriptors(registry, {}))
    # The catalog itself still answers, showing the tool as not yet described.
    stray_view = next(
        item for item in all_descriptors(registry, {}) if item.tool_id == "unguided_tool"
    )
    if guide is None:
        assert stray_view.guide.what == "Not described yet."
