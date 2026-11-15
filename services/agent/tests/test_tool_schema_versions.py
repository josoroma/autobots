"""A tool version's published schemas never change (Decision 0029 F13, refactor plan R-61).

An Expert's pinned grant, a recorded qualification and a saved run each name a tool by its version,
so a changed input or output schema is a new version, registered beside the old one and recorded in
domain/execution.py. The fixture holds each version's digest as the release that published it
emitted it, key order included.
"""

import hashlib
import json
from pathlib import Path

from autobots.adapters.tool_registry import tool_definitions
from autobots.application.tool_definitions import Browsing, ToolDefinition
from autobots.domain.execution import TOOL_VERSIONS

FIXTURE = json.loads((Path(__file__).parent / "fixtures/tool_schema_versions.json").read_text())
DIGESTS: dict[str, str] = FIXTURE["digests"]


def every_version() -> tuple[ToolDefinition, ...]:
    """Every definition any run can be granted, browse_goal included, as the catalog builds them."""
    return tool_definitions(None, workflow=True, browsing=Browsing(lambda: True))


def digest(tool: ToolDefinition) -> str:
    document = {
        "input": tool.input_model.model_json_schema(),
        "output": tool.output_model.model_json_schema(),
    }
    return hashlib.sha256(json.dumps(document).encode()).hexdigest()


def test_each_version_publishes_the_schemas_it_was_published_with() -> None:
    changed = sorted(
        f"{tool.tool_id}@{tool.version}"
        for tool in every_version()
        if DIGESTS.get(f"{tool.tool_id}@{tool.version}") not in {None, digest(tool)}
    )
    assert changed == [], "a changed schema is a new version (domain/execution.py)"


def test_the_fixture_names_each_registered_version_and_no_other() -> None:
    assert {f"{tool.tool_id}@{tool.version}" for tool in every_version()} == set(DIGESTS)


def test_each_tool_the_loop_offers_is_at_its_recorded_version() -> None:
    latest: dict[str, int] = {}
    for tool in every_version():
        latest[tool.tool_id] = max(latest.get(tool.tool_id, 0), tool.version)
    assert {tool: latest[tool] for tool in TOOL_VERSIONS} == dict(TOOL_VERSIONS)
