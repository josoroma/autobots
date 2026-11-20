"""US-15.25, US-16.6, US-17.5 and US-18.1: the concept seed's definitions. The database side runs
on a disposable stack."""

import json
from uuid import uuid4

from autobots.adapters.tool_registry import catalog
from autobots.contracts.browsing import BrowseGoalV3Input
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.workflows import input_errors, validate_graph
from autobots.operations.concept_seed import (
    DEEP_RESEARCH_INSTRUCTIONS,
    EXPERTS,
    GITHUB_RELEASE,
    GITHUB_TRIAGE,
    TRANSCRIPT_INSTRUCTIONS,
    TRANSCRIPT_SCHEMA,
    WORKFLOWS,
    available_tools,
)

GITHUB = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_TOKEN": "fake-token-for-tests"}


def test_the_eight_experts_and_eight_workflows_are_sd_02s() -> None:
    assert [expert.name for expert in EXPERTS] == [
        "Market watcher",
        "Research analyst",
        "Brief writer",
        "Issue triager",
        "Code maintainer",
        "Google bot",
        "Deep research writer",
        "Transcript reader",
    ]
    assert [workflow.name for workflow in WORKFLOWS] == [
        "Weekly competitor brief",
        "Monthly FX note",
        "Nightly test triage",
        "Interview synthesis",
        "Release notes from merged PRs",
        "Vendor due diligence",
        "Deep research content writer",
        "Transcript",
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
    # Tuned from the live runs (Decision 0034 E3): one plan, a document that fits one reply, and
    # never the document in a reply.
    assert "Never propose another" in DEEP_RESEARCH_INSTRUCTIONS
    assert "1,800 to 2,400 words" in DEEP_RESEARCH_INSTRUCTIONS
    assert "Never put the document in a reply" in DEEP_RESEARCH_INSTRUCTIONS
    assert "outputs/child-1/" in DEEP_RESEARCH_INSTRUCTIONS
    assert "read_artifact" in DEEP_RESEARCH_INSTRUCTIONS
    others = [
        item for item in EXPERTS if item.name not in ("Deep research writer", "Transcript reader")
    ]
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


def test_the_transcript_reader_browses_only_youtubes_hosts_and_publishes_one_file() -> None:
    """Decision 0035 Y13 and Y14: its grants, its purpose's hosts and terms, and its instructions'
    browse, stops and file."""
    expert = next(item for item in EXPERTS if item.name == "Transcript reader")
    assert expert.tools == ("browse_goal", "save_artifact", "publish_artifact")
    for host in ("youtube.com", "ytimg.com", "ggpht.com", "gstatic.com", "googlevideo.com"):
        assert host in expert.purpose and host in TRANSCRIPT_INSTRUCTIONS, host
    assert "never googlevideo.com" in expert.purpose and "terms" in expert.purpose
    for step in (
        '"...more"',
        '"Show transcript"',
        "bot_check",
        "no transcript",
        "transcript.md",
        "Source: ",
        "YouTube's own captions",
        "Never sign in, comment",
    ):
        assert step in TRANSCRIPT_INSTRUCTIONS, step
    assert "never" in TRANSCRIPT_INSTRUCTIONS.lower() and "summarise" in TRANSCRIPT_INSTRUCTIONS
    args = {
        "task": "t",
        "start_url": "https://www.youtube.com/watch?v=JWhICz1QR8M",
        "allowed_domains": ["youtube.com"],
        "output_schema": json.loads(TRANSCRIPT_SCHEMA),
    }
    assert BrowseGoalV3Input.model_validate(args).output_schema is not None
    config = ExpertConfig(
        purpose=expert.purpose, instructions=expert.instructions, tools=list(expert.tools)
    )
    assert config.browse_domains == []


def test_the_transcript_workflow_takes_only_a_watch_address_and_needs_browsing() -> None:
    """Decision 0035 Y14 and Y17: video, the Transcript reader, out; a draft without browse_goal."""
    workflow = next(item for item in WORKFLOWS if item.name == "Transcript")
    assert (workflow.needs, workflow.always_draft) == (("browse_goal",), False)
    graph = workflow.graph({expert.name: uuid4() for expert in EXPERTS})
    assert [(node["id"], node["block"]) for node in graph["nodes"]] == [
        ("video", "input"),
        ("transcribe", "agent"),
        ("out", "output"),
    ]
    for good in (
        "https://www.youtube.com/watch?v=JWhICz1QR8M&t=5s",
        "https://youtu.be/JWhICz1QR8M",
        "https://m.youtube.com/watch?v=JWhICz1QR8M",
    ):
        assert input_errors(graph, {"video": good}) == [], good
    for bad in (
        "http://www.youtube.com/watch?v=JWhICz1QR8M",
        "https://evil.test/watch?v=JWhICz1QR8M",
        "https://www.youtube.com/@channel",
        "https://www.youtube.com/results?search_query=x",
        "https://youtu.be/short",
        "https://www.youtube.com/watch?v=JWhICz1QR8M x",
    ):
        assert [(error.code, error.node) for error in input_errors(graph, {"video": bad})] == [
            ("input_pattern_mismatch", "video")
        ], bad


def test_the_market_watcher_and_its_monthly_note_have_no_inflation() -> None:
    """Decision 0036 R7: prices and exchange rates only, and "Monthly FX note" pulls the rates."""
    watcher = next(expert for expert in EXPERTS if expert.name == "Market watcher")
    assert "inflation_rates" not in watcher.tools and "market_history" in watcher.tools
    assert "inflation" not in watcher.purpose.lower()
    workflow = next(item for item in WORKFLOWS if item.name == "Monthly FX note")
    assert "inflation" not in workflow.description.lower()
    graph = workflow.graph({expert.name: uuid4() for expert in EXPERTS})
    labels = {node["id"]: node.get("label") for node in graph["nodes"]}
    assert (labels["in"], labels["pull"]) == ("Currency pairs", "Pull the rates")
    assert all(item.name != "Monthly FX and inflation note" for item in WORKFLOWS)
