"""The catalog lists exactly the tools the worker runs, from one composition edge (PRD-Tool-Catalog
TC-01, XMOD-01, PTOL-08). `browse_goal` is in both only while browsing is switched on and its
executor qualified (AB-02, Decision 0025 V6). With no runtime, a definition still describes itself
and refuses before any effect.
"""

import ast
import asyncio
import subprocess
import sys
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from pathlib import Path
from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel

from autobots.adapters import tool_registry
from autobots.adapters.tool_middleware import visible_tools
from autobots.adapters.tool_registry import build_registry, catalog_registry
from autobots.application import browsing_tool, worker_inference
from autobots.application.artifacts import PingableObjectStore
from autobots.application.assignments import Delegation
from autobots.application.provider_settings import ProviderContext
from autobots.application.run_lifecycle import LoopConfig, LoopResult, NoToolSet, pass_registry
from autobots.application.run_usage import RootLimits
from autobots.application.sql import SqlParams
from autobots.application.tool_catalog import describe
from autobots.application.tool_definitions import (
    Browsing,
    ToolContext,
    ToolFailed,
    ToolRegistry,
    ToolScope,
)
from autobots.application.tool_gateway import ToolGateway
from autobots.application.worker_inference import CatalogCache, InferenceSource
from autobots.application.worker_leases import Lease
from autobots.domain.models import ModelRoute
from autobots.operations import worker
from sql_fakes import ScriptedConnection, ScriptedRows

SWITCHED_ON = {"AUTOBOTS_BROWSER_EXECUTOR": "enabled"}
ROUTE = ModelRoute("researcher", "openrouter_terra", "fixture/model", 1)


async def never_drive(*_: object) -> LoopResult:
    raise AssertionError("describing or comparing tools drives no child")


DELEGATION = Delegation(never_drive, RootLimits(), lease_seconds=1.0)
# Never used: these tests compare and describe tools, and run none.
STORE = cast("PingableObjectStore", object())


def ids(registry: ToolRegistry) -> set[tuple[str, int]]:
    return {(tool.tool_id, tool.version) for tool in registry.definitions()}


def qualified(state: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """The live check's verdict, the second half of `executor_ready` (AB-02)."""
    monkeypatch.setattr(browsing_tool, "executor_qualified", lambda *_: state)


def worker_browsing(
    view: Mapping[str, str], monkeypatch: pytest.MonkeyPatch, bound: bool = True
) -> Browsing | None:
    """What the worker's binder sets for one job, for a workspace whose Keys & vars are `view`."""

    async def sources(*_: object) -> Mapping[str, str]:
        return view

    async def role_route(*_: object) -> tuple[object, ModelRoute] | str:
        return (object(), ROUTE) if bound else "route_not_bound"

    monkeypatch.setattr(worker_inference, "key_sources", sources)
    monkeypatch.setattr(InferenceSource, "role_route", role_route)
    source = InferenceSource(
        "postgresql://unused",
        cast("ProviderContext", None),
        cast("CatalogCache", None),
        browser=object(),
    )
    job = Lease(uuid4(), uuid4(), 1, "worker", 1, "running")
    return asyncio.run(source._browsing(ScriptedConnection(), job))


def worker_registry(browsing: Browsing | None, *, workflow: bool) -> ToolRegistry:
    """The registry a pass builds from the worker's own config, as its binder left it. An
    inference worker always has its object store (operations/worker.inference_from_environment)."""
    config = replace(worker.loop_config(STORE), browsing=browsing)
    return pass_registry(config, DELEGATION, workflow=workflow)


def test_the_catalog_lists_what_a_qualified_worker_builds_for_a_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified(True, monkeypatch)
    browsing = worker_browsing(SWITCHED_ON, monkeypatch)
    assert browsing is not None
    built = worker_registry(browsing, workflow=True)
    assert ids(catalog_registry(SWITCHED_ON)) == ids(built)
    assert ("browse_goal", 1) in ids(built)
    assert ("workflow_approval", 1) in ids(built)


@pytest.mark.parametrize(
    ("switch", "verdict"), [("disabled", True), ("enabled", False), ("", False)]
)
def test_without_both_the_switch_and_the_qualification_neither_has_browse_goal(
    monkeypatch: pytest.MonkeyPatch, switch: str, verdict: bool
) -> None:
    qualified(verdict, monkeypatch)
    view = {"AUTOBOTS_BROWSER_EXECUTOR": switch}
    browsing = worker_browsing(view, monkeypatch)
    assert browsing is None
    listed = ids(catalog_registry(view))
    assert listed == ids(worker_registry(browsing, workflow=True))
    assert ("browse_goal", 1) not in listed


def test_a_run_without_a_researcher_route_has_no_browsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified(True, monkeypatch)
    assert worker_browsing(SWITCHED_ON, monkeypatch, bound=False) is None


def test_a_goal_pass_has_every_tool_but_the_workflow_step() -> None:
    goal = ids(worker_registry(None, workflow=False))
    assert goal | {("workflow_approval", 1)} == ids(catalog_registry({}))
    assert ("workflow_approval", 1) not in goal


def visible(config: LoopConfig) -> list[str]:
    """The tools a pass shows its model when its scope grants every one (SP-013)."""
    registry = pass_registry(config, DELEGATION)
    every = {tool.tool_id: tool.version for tool in catalog_registry({}).definitions()}
    scope = ToolScope(uuid4(), uuid4(), 1, every, ("outputs",))
    return [tool.name for tool in visible_tools(ToolGateway(registry), scope)]


def test_a_pass_without_an_object_store_never_shows_publish_artifact() -> None:
    """A pass shows its model only tools it can use: without a store there is no publish tool,
    even granted, while the catalog still describes it."""
    from autobots.application.goal_loop import UNBOUND

    storeless = LoopConfig(route=UNBOUND, tool_set=build_registry)
    assert "publish_artifact" not in visible(storeless)
    assert "publish_artifact" in visible(replace(storeless, object_store=STORE))
    assert catalog_registry({}).get("publish_artifact", 1) is not None


def test_a_pass_without_a_tool_set_is_refused() -> None:
    from autobots.application.goal_loop import UNBOUND

    with pytest.raises(NoToolSet):
        pass_registry(LoopConfig(route=UNBOUND), DELEGATION)


def test_the_config_adds_its_own_definitions_after_the_tool_set() -> None:
    calculate = next(t for t in build_registry(None).definitions() if t.tool_id == "calculate")
    extra = replace(calculate, tool_id="fixture_tool")
    config = replace(worker.loop_config(None), tools=(extra,))
    assert ("fixture_tool", 1) in ids(pass_registry(config, DELEGATION))


class Untouchable:
    """A connection that fails the test on any use, so a refusal is proved to come first."""

    async def execute(self, query: str, _params: SqlParams | None = None, /) -> ScriptedRows:
        raise AssertionError(f"a definition with no runtime touched the connection: {query}")

    def transaction(self) -> AbstractAsyncContextManager[None]:
        raise AssertionError("a definition with no runtime touched the connection: transaction")


ARGUMENTS: dict[str, dict[str, object]] = {
    "propose_plan": {
        "tasks": [{"id": "t1", "title": "Read the file", "expected_evidence": "outputs/a.md"}]
    },
    "publish_artifact": {"path": "outputs/a.md", "version": 1},
    "assign_specialist": {"expert_id": str(uuid4()), "goal": "Help"},
    "browse_goal": {
        "task": "What is example.com for?",
        "start_url": "https://example.com/",
        "allowed_domains": ["example.com"],
    },
}


def test_with_no_runtime_each_definition_describes_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    qualified(True, monkeypatch)
    registry = catalog_registry(SWITCHED_ON)
    for tool in registry.definitions():
        described = describe(tool, {})
        assert (described.tool_id, described.version) == (tool.tool_id, tool.version)
        assert described.input_schema == tool.input_model.model_json_schema()


@pytest.mark.parametrize("tool_id", sorted(ARGUMENTS))
@pytest.mark.asyncio
async def test_with_no_runtime_a_bound_definition_refuses_before_any_effect(
    monkeypatch: pytest.MonkeyPatch, tool_id: str
) -> None:
    qualified(True, monkeypatch)
    registry = catalog_registry(SWITCHED_ON)
    tool = next(t for t in registry.definitions() if t.tool_id == tool_id)
    arguments: BaseModel = tool.input_model.model_validate(ARGUMENTS[tool_id])
    scope = ToolScope(uuid4(), uuid4(), 1, {tool_id: tool.version}, ("outputs",))
    context = ToolContext(Untouchable(), scope, "operation")

    async def call() -> BaseModel:
        return await tool.handler(arguments, context)

    with pytest.raises(ToolFailed) as refused:
        await call()
    assert str(refused.value) in {"tool_runtime_unbound", "browsing_unavailable"}


def test_the_catalog_registry_reads_the_workspace_view_at_each_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`browse_goal`'s qualification is read again at each call, as the worker's is (AB-02)."""
    qualified(True, monkeypatch)
    tool = catalog_registry(SWITCHED_ON).get("browse_goal", 1)
    assert tool is not None and tool.executor_qualified()
    qualified(False, monkeypatch)
    assert not tool.executor_qualified()


def importers_of_the_edge(source: Path) -> list[str]:
    """Modules under `source` that import adapters/tool_registry.py, function-level imports too."""
    found = []
    for path in sorted(source.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            named = (
                isinstance(node, ast.ImportFrom)
                and (
                    node.module == "autobots.adapters.tool_registry"
                    or (
                        node.module == "autobots.adapters"
                        and any(alias.name == "tool_registry" for alias in node.names)
                    )
                )
            ) or (
                isinstance(node, ast.Import)
                and any(alias.name == "autobots.adapters.tool_registry" for alias in node.names)
            )
            if named:
                found.append(str(path.relative_to(source)))
                break
    return found


def test_only_the_api_and_the_worker_import_the_composition_edge() -> None:
    """XMOD-01: application/ receives what api/ and operations/ built, and never imports it."""
    source = Path(tool_registry.__file__).resolve().parents[1]
    importers = importers_of_the_edge(source)
    assert importers and all(path.startswith(("api/", "operations/")) for path in importers)


def test_the_import_check_sees_a_planted_application_import(tmp_path: Path) -> None:
    (tmp_path / "application").mkdir()
    (tmp_path / "application/late.py").write_text(
        "def later() -> None:\n    from autobots.adapters import tool_registry\n"
    )
    assert importers_of_the_edge(tmp_path) == ["application/late.py"]


def test_building_the_api_loads_neither_the_goal_loop_nor_deep_agents() -> None:
    """The catalog no longer reaches the agent runtime, so neither the app factory nor the
    process entry point, `autobots.api.main`, loads it (XMOD-01)."""
    probe = (
        "import sys, autobots.api.app, autobots.api.main; "
        "print(sorted(m for m in ('autobots.application.goal_loop', 'deepagents') "
        "if m in sys.modules))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True, timeout=120
    )
    assert loaded.stdout.strip() == "[]"
