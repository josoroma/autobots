"""US-15.25 and US-16.6: the concept seed's definitions. The database side runs on a disposable
stack."""

from uuid import uuid4

from autobots.adapters.tool_registry import catalog
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.workflows import validate_graph
from autobots.operations.concept_seed import (
    DEEP_RESEARCH_INSTRUCTIONS,
    EXPERTS,
    GITHUB_RELEASE,
    GITHUB_TRIAGE,
    WORKFLOWS,
    available_tools,
)

GITHUB = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "fake-token-for-tests"}


def test_the_seven_experts_and_seven_workflows_are_sd_02s() -> None:
    assert [expert.name for expert in EXPERTS] == [
        "Market watcher",
        "Research analyst",
        "Brief writer",
        "Issue triager",
        "Code maintainer",
        "Google bot",
        "Deep research writer",
    ]
    assert [workflow.name for workflow in WORKFLOWS] == [
        "Weekly competitor brief",
        "Monthly FX and inflation note",
        "Nightly test triage",
        "Interview synthesis",
        "Release notes from merged PRs",
        "Vendor due diligence",
        "Deep research content writer",
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
    tools = catalog()
    without, with_github = available_tools({}, tools), available_tools(GITHUB, tools)
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


def test_the_deep_research_writer_is_decision_0034s() -> None:
    """E1 to E4: its purpose, its eight tools, and instructions for both of its roles."""
    expert = next(item for item in EXPERTS if item.name == "Deep research writer")
    assert expert.tools == (
        "google_search",
        "google_extract",
        "search_web",
        "extract_website_content",
        "read_artifact",
        "read_run_file",
        "save_artifact",
        "publish_artifact",
    )
    assert "Deep-Research-Content-Writer" in expert.purpose
    assert expert.instructions == DEEP_RESEARCH_INSTRUCTIONS
    config = ExpertConfig(
        purpose=expert.purpose, instructions=expert.instructions, tools=list(expert.tools)
    )
    assert config.instructions == DEEP_RESEARCH_INSTRUCTIONS
    for phase in ("search", "collect", "synthesize", "write", "check", "publish"):
        assert phase in DEEP_RESEARCH_INSTRUCTIONS.lower(), phase
    for path in (
        "<outputs>/research/sources.md",
        "<outputs>/research/synthesis.md",
        "<outputs>/content.md",
        "<outputs>/report.md",
        "<outputs>/review.md",
    ):
        assert path in DEEP_RESEARCH_INSTRUCTIONS, path
    assert "artifact_ids" in DEEP_RESEARCH_INSTRUCTIONS
    assert "outputs/child-1/" in DEEP_RESEARCH_INSTRUCTIONS
    assert "read_artifact" in DEEP_RESEARCH_INSTRUCTIONS
    others = [item for item in EXPERTS if item.name != "Deep research writer"]
    assert all(item.instructions == "" for item in others)


def test_the_deep_research_workflow_reviews_its_first_step_and_needs_google() -> None:
    """F1 and F2: research and write, then check and report, both by the Deep research writer,
    and an approval before the output. Without SerpApi, it is seeded as a draft."""
    workflow = next(item for item in WORKFLOWS if item.name == "Deep research content writer")
    experts = {expert.name: uuid4() for expert in EXPERTS}
    graph = WorkflowGraph.model_validate(workflow.graph(experts))
    blocks = [(node.id, node.block, node.label) for node in graph.nodes]
    assert blocks == [
        ("in", "input", None),
        ("research", "agent", "Research and write"),
        ("s1", "transform", None),
        ("check", "agent", "Check and report"),
        ("gate", "approval", None),
        ("out", "output", None),
    ]
    writer = str(experts["Deep research writer"])
    agents = [node for node in graph.nodes if node.block == "agent"]
    assert all(str(node.config["expert_id"]) == writer for node in agents)
    assert [(link.source, link.target, link.target_port) for link in graph.links] == [
        ("in", "research", "goal"),
        ("research", "s1", "value"),
        ("s1", "check", "goal"),
        ("check", "gate", "value"),
        ("gate", "out", "value"),
    ]
    assert (workflow.needs, workflow.always_draft) == (("google_search",), False)
    tools = catalog()
    assert "google_search" not in available_tools({}, tools)
    assert "google_search" in available_tools({"SERPAPI_API_KEY": "fake-serpapi-key"}, tools)
