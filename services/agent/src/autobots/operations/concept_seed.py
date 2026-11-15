"""US-15.25, PRD-Studio SD-01 and SD-02, Decision 0022 D17: the concept Experts and workflows,
seeded into one workspace an operator names.

Run it with `python -m autobots.operations.concept_seed --workspace <id>`. It is not a migration,
and running migrations creates none of this. It is repeatable: an Expert or workflow that already
has its name in the workspace is left exactly as it is, so a second run, or a person's later edit,
is never overwritten. It writes no key, token or password, and admits no run, so nothing is left
pending.

An Expert whose tool is unavailable on this install is saved without it, and its purpose says so. A
workflow whose steps need an unavailable tool (SD-02) is saved as a draft and not published, and
Interview synthesis stays a draft until a workflow execution can carry files.
"""

import argparse
import asyncio
import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise
from typing import Any
from uuid import UUID

import psycopg

from autobots.adapters.tool_registry import catalog
from autobots.application.experts import create_expert
from autobots.application.sql import SqlConnection
from autobots.application.tool_catalog import Catalog
from autobots.application.workflows import create_workflow, publish_version, save_draft
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.workflows import WorkflowGraph
from autobots.operations.cli import Refused, command, uuid_argument
from autobots.operations.composition import DATABASE_URL, require


@dataclass(frozen=True)
class ExpertSeed:
    name: str
    purpose: str
    tools: tuple[str, ...]


EXPERTS = (
    ExpertSeed(
        "Market watcher",
        "Tracks prices, exchange rates and inflation, and explains what moved and why it matters.",
        (
            "market_history",
            "inflation_rates",
            "calculate",
            "read_csv",
            "save_artifact",
            "publish_artifact",
        ),
    ),
    ExpertSeed(
        "Research analyst",
        "Searches the web and reads sources carefully. Cites every claim and flags anything it "
        "couldn't confirm.",
        (
            "search_web",
            "extract_website_content",
            "tavily_search",
            "tavily_extract",
            "save_artifact",
            "publish_artifact",
        ),
    ),
    ExpertSeed(
        "Brief writer",
        "Turns findings into a short brief with a recommendation, a comparison table and numbered "
        "sources.",
        ("read_run_file", "save_artifact", "publish_artifact"),
    ),
    ExpertSeed(
        "Issue triager",
        "Groups failing checks by cause and drafts one GitHub issue per distinct failure. Each "
        "issue waits for you.",
        ("read_csv", "github_list_workflow_runs", "github_search_issues", "create_github_issue"),
    ),
    ExpertSeed(
        "Code maintainer",
        "Reads the repository, edits copies in the run's files, and proposes a pull request that "
        "waits for you.",
        (
            "github_read_file",
            "search_files",
            "read_code_file",
            "patch_code_file",
            "write_code_file",
            "github_open_pull_request",
        ),
    ),
)


def _node(name: str, block: str, label: str | None = None, **config: Any) -> dict[str, Any]:
    node: dict[str, Any] = {"id": name, "block": block, "version": 1, "config": config}
    if label is not None:
        node["label"] = label
    return node


def _link(source: str, source_port: str, target: str, target_port: str) -> dict[str, str]:
    return {
        "source": source,
        "source_port": source_port,
        "target": target,
        "target_port": target_port,
    }


def _agent(name: str, label: str, expert: str, experts: Mapping[str, UUID]) -> dict[str, Any]:
    return _node(name, "agent", label, expert_id=str(experts[expert]))


def _text(name: str) -> dict[str, Any]:
    """An agent's result is JSON and the next agent's goal is text, so a transform sits between."""
    return _node(name, "transform", operation="to_string")


def _chain(steps: Sequence[tuple[str, str]]) -> list[dict[str, str]]:
    return [
        _link(source, port, target, target_port(target))
        for (source, port), (target, _) in pairwise(steps)
    ]


def target_port(name: str) -> str:
    return {"read": "path", "each": "items"}.get(name, _PORTS.get(name, "value"))


# The input port of each named node, where it isn't `value`.
_PORTS = {
    "gather": "goal",
    "compare": "goal",
    "write": "goal",
    "pull": "goal",
    "find": "goal",
    "file": "goal",
    "synth": "goal",
    "collect": "goal",
    "research": "goal",
}


@dataclass(frozen=True)
class WorkflowSeed:
    name: str
    description: str
    # Tools whose absence makes this a draft (SD-02). Empty with `always_draft` false: published.
    needs: tuple[str, ...]
    always_draft: bool
    graph: Callable[[Mapping[str, UUID]], dict[str, Any]]


def _weekly(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="string"),
        _agent("gather", "Gather sources", "Research analyst", experts),
        _text("s1"),
        _agent("compare", "Compare plans and prices", "Research analyst", experts),
        _text("s2"),
        _agent("write", "Write the brief", "Brief writer", experts),
        _node("gate", "approval"),
        _node("out", "output"),
    ]
    order = [
        ("in", "value"),
        ("gather", "result"),
        ("s1", "value"),
        ("compare", "result"),
        ("s2", "value"),
        ("write", "result"),
        ("gate", "value"),
        ("out", ""),
    ]
    return {"ir_version": 2, "nodes": nodes, "links": _chain(order)}


def _monthly(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="string"),
        _agent("pull", "Pull rates and inflation", "Market watcher", experts),
        _text("s1"),
        _agent("write", "Write the note", "Brief writer", experts),
        _node("out", "output"),
    ]
    order = [("in", "value"), ("pull", "result"), ("s1", "value"), ("write", "result"), ("out", "")]
    return {"ir_version": 2, "nodes": nodes, "links": _chain(order)}


def _triage(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="string"),
        _agent("find", "Find failures and duplicates", "Issue triager", experts),
        _node("gate", "approval"),
        _text("s1"),
        _agent("file", "File one issue per failure", "Issue triager", experts),
        _node("out", "output"),
    ]
    order = [
        ("in", "value"),
        ("find", "result"),
        ("gate", "value"),
        ("s1", "value"),
        ("file", "result"),
        ("out", ""),
    ]
    return {"ir_version": 2, "nodes": nodes, "links": _chain(order)}


def _interviews(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="string"),
        _node("read", "read"),
        _agent("synth", "Synthesize themes", "Brief writer", experts),
        _node("out", "output"),
    ]
    order = [("in", "value"), ("read", "content"), ("synth", "result"), ("out", "")]
    return {"ir_version": 2, "nodes": nodes, "links": _chain(order)}


def _release(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="string"),
        _agent("collect", "Collect merged PRs", "Code maintainer", experts),
        _text("s1"),
        _agent("write", "Write the notes", "Brief writer", experts),
        _node("gate", "approval"),
        _node("out", "output"),
    ]
    order = [
        ("in", "value"),
        ("collect", "result"),
        ("s1", "value"),
        ("write", "result"),
        ("gate", "value"),
        ("out", ""),
    ]
    return {"ir_version": 2, "nodes": nodes, "links": _chain(order)}


def _vendors(experts: Mapping[str, UUID]) -> dict[str, Any]:
    nodes = [
        _node("in", "input", type="list"),
        _node("each", "foreach", max_items=10, item_type="string"),
        _agent("research", "Research the vendor", "Research analyst", experts),
        _node("all", "join"),
        _text("s1"),
        _agent("compare", "Compare and recommend", "Brief writer", experts),
        _node("gate", "approval"),
        _node("out", "output"),
    ]
    links = [
        _link("in", "value", "each", "items"),
        _link("each", "item", "research", "goal"),
        _link("research", "result", "all", "value"),
        _link("all", "items", "s1", "value"),
        _link("s1", "value", "compare", "goal"),
        _link("compare", "result", "gate", "value"),
        _link("gate", "value", "out", "value"),
    ]
    return {"ir_version": 2, "nodes": nodes, "links": links}


GITHUB_TRIAGE = ("github_list_workflow_runs", "github_search_issues", "create_github_issue")
GITHUB_RELEASE = ("github_read_file", "github_open_pull_request")
WORKFLOWS = (
    WorkflowSeed(
        "Weekly competitor brief",
        "Name the competitors and the question. Sources are gathered and compared, and a brief "
        "waits for your approval.",
        (),
        False,
        _weekly,
    ),
    WorkflowSeed(
        "Monthly FX and inflation note",
        "Name the currency pairs and countries. Rates and inflation are pulled into a short note.",
        (),
        False,
        _monthly,
    ),
    WorkflowSeed(
        "Nightly test triage",
        "Name the workflow file and branch. Failures are grouped, and each issue waits for you "
        "before it's filed.",
        GITHUB_TRIAGE,
        False,
        _triage,
    ),
    WorkflowSeed(
        "Interview synthesis",
        "Name the notes file. Its themes are synthesized. A draft until an execution can carry "
        "files.",
        (),
        True,
        _interviews,
    ),
    WorkflowSeed(
        "Release notes from merged PRs",
        "Name the date and base branch. Merged pull requests become release notes that wait for "
        "you.",
        GITHUB_RELEASE,
        False,
        _release,
    ),
    WorkflowSeed(
        "Vendor due diligence",
        "List the vendors and the criteria. Each vendor is researched, then compared, and the "
        "recommendation waits for you.",
        (),
        False,
        _vendors,
    ),
)


def available_tools(environ: Mapping[str, str], tools: Catalog) -> frozenset[str]:
    return frozenset(
        item.tool_id for item in tools.descriptors(environ) if item.availability == "available"
    )


async def _named(
    connection: SqlConnection, table: str, workspace_id: UUID, name: str
) -> UUID | None:
    cursor = await connection.execute(
        f"select id from {table} where workspace_id = %s and name = %s",
        (workspace_id, name),
    )
    row = await cursor.fetchone()
    return None if row is None else UUID(str(row[0]))


class NoOwner(Refused):
    """The workspace has no owner to seed as."""


async def _owner(connection: SqlConnection, workspace_id: UUID) -> UUID:
    cursor = await connection.execute(
        "select user_id from public.workspace_members where workspace_id = %s and role = 'owner' "
        "order by user_id limit 1",
        (workspace_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        raise NoOwner("that workspace has no owner, so nothing was seeded")
    return UUID(str(row[0]))


async def _seed_experts(
    connection: SqlConnection,
    workspace_id: UUID,
    actor: UUID,
    usable: frozenset[str],
    tools: Catalog,
) -> tuple[dict[str, UUID], dict[str, Any]]:
    """Each concept Expert's ID by name, and what happened to each: "kept", or what was created."""
    experts: dict[str, UUID] = {}
    report: dict[str, Any] = {}
    for expert in EXPERTS:
        found = await _named(connection, "public.experts", workspace_id, expert.name)
        if found is not None:
            experts[expert.name] = found
            report[expert.name] = "kept"
            continue
        granted = [tool for tool in expert.tools if tool in usable]
        missing = [tool for tool in expert.tools if tool not in usable]
        purpose = expert.purpose
        if missing:
            purpose += (
                f" Saved without {', '.join(missing)}, which this install can't offer yet. Add "
                "them once their keys are set."
            )
        view = await create_expert(
            connection,
            workspace_id=workspace_id,
            actor_id=actor,
            idempotency_key=f"concept-seed:expert:{expert.name}",
            name=expert.name,
            config=ExpertConfig(purpose=purpose, tools=granted),
            catalog=tools,
        )
        experts[expert.name] = view.id
        report[expert.name] = {"created": True, "without": missing}
    return experts, report


async def _seed_workflows(
    connection: SqlConnection,
    workspace_id: UUID,
    actor: UUID,
    usable: frozenset[str],
    experts: Mapping[str, UUID],
) -> dict[str, Any]:
    """What happened to each concept workflow: "kept", left a draft, or published."""
    report: dict[str, Any] = {}
    for workflow in WORKFLOWS:
        if await _named(connection, "public.workflows", workspace_id, workflow.name) is not None:
            report[workflow.name] = "kept"
            continue
        flow = await create_workflow(
            connection,
            workspace_id=workspace_id,
            actor_id=actor,
            idempotency_key=f"concept-seed:workflow:{workflow.name}",
            name=workflow.name,
            description=workflow.description,
        )
        graph = WorkflowGraph.model_validate(workflow.graph(experts))
        unavailable = [tool for tool in workflow.needs if tool not in usable]
        if workflow.always_draft or unavailable:
            await save_draft(connection, workspace_id, actor, flow.id, graph)
            report[workflow.name] = {"draft": True, "unavailable": unavailable}
        else:
            await publish_version(
                connection,
                workspace_id=workspace_id,
                actor_id=actor,
                workflow_id=flow.id,
                idempotency_key=f"concept-seed:publish:{workflow.name}",
                expected_version=0,
                graph=graph,
                source="user",
            )
            report[workflow.name] = {"published": 1}
    return report


async def seed(
    connection: SqlConnection, workspace_id: UUID, environ: Mapping[str, str]
) -> dict[str, Any]:
    """Each concept Expert and workflow once. What already exists by name is kept as it is.

    The owner, then the Experts, then the workflows that name them (POPS-20). Raises `NoOwner`, a
    refusal, before anything is written when the workspace has no owner.
    """
    actor = await _owner(connection, workspace_id)
    tools = catalog()
    usable = available_tools(environ, tools)
    experts, expert_report = await _seed_experts(connection, workspace_id, actor, usable, tools)
    workflow_report = await _seed_workflows(connection, workspace_id, actor, usable, experts)
    return {"experts": expert_report, "workflows": workflow_report}


async def _main(workspace: UUID, environ: Mapping[str, str]) -> int:
    (url,) = require(environ, DATABASE_URL)
    async with await psycopg.AsyncConnection.connect(url, autocommit=True) as connection:
        report = await seed(connection, workspace, environ)
    print(json.dumps(report))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Exit codes: 0 seeded, 1 refused, 2 not configured (`cli.py`)."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--workspace", type=uuid_argument, required=True)
    arguments = parser.parse_args(argv)
    return command(lambda: asyncio.run(_main(arguments.workspace, os.environ)))


if __name__ == "__main__":
    raise SystemExit(main())
