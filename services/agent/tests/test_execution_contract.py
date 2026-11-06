"""The compatibility rule, and the table it reads staying equal to what the loop really offers."""

import json
from typing import Any

import pytest

from autobots.adapters.checkpoints import QUALIFIED_STACK, adapter_identity
from autobots.application.assignments import Delegation
from autobots.application.goal_loop import loop_registry
from autobots.application.run_usage import RootLimits
from autobots.application.runs import _snapshot
from autobots.application.worker_inference import frozen_policy
from autobots.domain.execution import (
    GRAPH_STATE_VERSION,
    TOOL_VERSIONS,
    current_contract,
    incompatibility,
)
from autobots.domain.models import UnknownModelProfile, resolve_role_policy


def test_the_version_table_is_what_the_registry_offers() -> None:
    async def drive(*_: Any) -> Any:
        return None

    delegation = Delegation(drive=drive, limits=RootLimits(), lease_seconds=1)
    registry = loop_registry(RootLimits(), object_store=object(), delegation=delegation)
    assert registry.versions() == dict(TOOL_VERSIONS)


def test_a_run_under_the_current_contract_can_continue() -> None:
    assert incompatibility(current_contract()) is None


def test_an_older_contract_with_fewer_tools_can_continue() -> None:
    assert incompatibility({"graph_state": GRAPH_STATE_VERSION, "tools": {"calculate": 1}}) is None


def test_nothing_recorded_is_blocked() -> None:
    assert incompatibility(None) == "no execution contract is recorded"


def test_unknown_graph_state_is_blocked() -> None:
    assert "graph state 99" in (incompatibility({"graph_state": 99, "tools": {}}) or "")


def test_a_changed_tool_is_blocked_with_its_versions() -> None:
    recorded = {"graph_state": GRAPH_STATE_VERSION, "tools": {"save_artifact": 0}}
    assert incompatibility(recorded) == "save_artifact changed from v0 to v1"


def test_a_removed_tool_is_blocked() -> None:
    recorded = {"graph_state": GRAPH_STATE_VERSION, "tools": {"old_tool": 1}}
    assert incompatibility(recorded) == "old_tool v1 no longer exists"


def test_the_adapter_identity_names_the_pinned_release() -> None:
    version, fingerprint = adapter_identity()
    assert version == "3.2.0"
    assert len(fingerprint) == 64
    assert adapter_identity() == (version, fingerprint)


def test_a_snapshot_records_its_models_and_a_changed_mapping_stops_the_run() -> None:
    snapshot = json.loads(_snapshot(resolve_role_policy(run_profile="openrouter_deepseek_flash")))
    assert frozen_policy(snapshot).bindings
    route = snapshot["routes"]["openrouter_deepseek_flash"]
    assert route["wire_id"] == "deepseek/deepseek-v4.1-flash-1017"
    route["wire_id"] = "deepseek/some-other-model"
    with pytest.raises(UnknownModelProfile):
        frozen_policy(snapshot)


def test_a_snapshot_saved_before_routes_were_recorded_still_reads() -> None:
    snapshot = json.loads(_snapshot(resolve_role_policy()))
    del snapshot["routes"]
    assert frozen_policy(snapshot).bindings


def test_the_qualification_covers_the_framework_stack() -> None:
    assert {"langgraph", "langgraph-checkpoint", "deepagents"} <= set(QUALIFIED_STACK)
