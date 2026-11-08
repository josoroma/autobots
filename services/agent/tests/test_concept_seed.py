"""US-15.25: the concept seed's definitions. The database side runs on a disposable stack."""

from uuid import uuid4

from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.workflows import validate_graph
from autobots.operations.concept_seed import (
    EXPERTS,
    GITHUB_RELEASE,
    GITHUB_TRIAGE,
    WORKFLOWS,
    available_tools,
)

GITHUB = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "fake-token-for-tests"}


def test_the_five_experts_and_six_workflows_are_sd_02s() -> None:
    assert [expert.name for expert in EXPERTS] == [
        "Market watcher",
        "Research analyst",
        "Brief writer",
        "Issue triager",
        "Code maintainer",
    ]
    assert [workflow.name for workflow in WORKFLOWS] == [
        "Weekly competitor brief",
        "Monthly FX and inflation note",
        "Nightly test triage",
        "Interview synthesis",
        "Release notes from merged PRs",
        "Vendor due diligence",
    ]


def test_every_workflow_graph_is_valid_and_each_agent_step_names_its_expert() -> None:
    experts = {expert.name: uuid4() for expert in EXPERTS}
    for workflow in WORKFLOWS:
        graph = WorkflowGraph.model_validate(workflow.graph(experts))
        assert validate_graph(graph.model_dump(mode="json")) == [], workflow.name
        agents = [node for node in graph.nodes if node.block == "agent"]
        assert agents and all(node.label for node in agents), workflow.name
        assert {str(node.config["expert_id"]) for node in agents} <= {
            str(value) for value in experts.values()
        }


def test_the_github_tools_are_unavailable_until_both_variables_are_set() -> None:
    without, with_github = available_tools({}), available_tools(GITHUB)
    for tool in (*GITHUB_TRIAGE, *GITHUB_RELEASE):
        assert tool not in without
        assert tool in with_github
    assert {"calculate", "save_artifact", "read_csv"} <= without


def test_every_concept_expert_that_saves_can_publish() -> None:
    """Decision 0023 E7: verification needs a published file from every run, a workflow's
    delegated step included, so an Expert that saves files is granted publish_artifact too."""
    for expert in EXPERTS:
        if "save_artifact" in expert.tools:
            assert "publish_artifact" in expert.tools, expert.name
