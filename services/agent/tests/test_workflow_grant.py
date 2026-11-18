"""The tools a workflow execution's run is granted, with plain values (PRD 7.3, PPRD-16).

With no request it gets every workflow tool. A request narrows it to the named workflow tools, and
it always keeps the plan tools and the approval step. Order follows WORKFLOW_TOOLS, so the grant a
run's admission fingerprints is unchanged (tests/test_run_admission.py pins it).
"""

from autobots.domain.tools import (
    PLAN_TOOLS,
    WORKFLOW_APPROVAL_TOOL,
    WORKFLOW_TOOLS,
    workflow_grant,
)


def test_no_request_grants_every_workflow_tool() -> None:
    assert workflow_grant(None) is WORKFLOW_TOOLS


def test_a_request_keeps_the_plan_tools_and_the_approval_step_in_order() -> None:
    granted = workflow_grant(["read_csv", "calculate", "not_a_tool"])
    assert list(granted.items()) == [
        ("propose_plan", 1),
        ("complete_task", 1),
        ("read_offload", 1),
        ("calculate", 1),
        ("read_csv", 1),
        (WORKFLOW_APPROVAL_TOOL, 1),
    ]


def test_an_empty_request_grants_only_what_every_execution_has() -> None:
    assert dict(workflow_grant([])) == {**PLAN_TOOLS, WORKFLOW_APPROVAL_TOOL: 1}


def test_a_request_never_widens_beyond_the_workflow_tools() -> None:
    granted = workflow_grant(["github_open_pull_request", "assign_specialist"])
    assert set(granted) == {*PLAN_TOOLS, "assign_specialist", WORKFLOW_APPROVAL_TOOL}


def test_agent_steps_get_their_experts_tools_and_a_request_still_narrows_them() -> None:
    """Decision 0034 F3: each agent step's child is granted its Expert's tools, which the
    child's grant intersects with this one. A requested list narrows them like the rest."""
    agents = {"google_search": 1, "read_artifact": 1, "save_artifact": 1}
    granted = workflow_grant(None, agents)
    assert {"google_search", "read_artifact"} <= set(granted)
    assert {**WORKFLOW_TOOLS} == {tool: granted[tool] for tool in WORKFLOW_TOOLS}
    assert workflow_grant(None, {}) is WORKFLOW_TOOLS
    narrowed = workflow_grant(["read_artifact"], agents)
    assert "read_artifact" in narrowed
    assert "google_search" not in narrowed
