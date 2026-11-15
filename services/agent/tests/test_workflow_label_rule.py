"""PRD-Studio WF-06's label rule, run on the cases the workflow editor's copy also reads.

The domain's `ir_normalized` owns the rule. The editor keeps one copy in
apps/web/lib/workflow-ir.ts, and both run contracts/fixtures/workflow-label-rule.json, so the two
can't disagree on any case (Decision 0029 F1). A graph left with no label keeps an IR version it
declares, so no stored hash changes.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from autobots.contracts.workflows import WorkflowGraph
from autobots.domain.workflows import graph_hash, ir_normalized, validate_graph

REPOSITORY = Path(__file__).resolve().parents[3]
CASES: list[dict[str, Any]] = json.loads(
    (REPOSITORY / "contracts/fixtures/workflow-label-rule.json").read_text()
)
NAMES = [case["name"] for case in CASES]


def _stored(graph: dict[str, Any]) -> dict[str, Any]:
    """What the API stores for a graph it receives: read through the contract, then normalized."""
    return ir_normalized(WorkflowGraph.model_validate(graph).model_dump(mode="json"))


@pytest.mark.parametrize("case", CASES, ids=NAMES)
def test_the_domain_normalizes_each_shared_case(case: dict[str, Any]) -> None:
    assert ir_normalized(case["graph"]) == case["normalized"]


@pytest.mark.parametrize("case", CASES, ids=NAMES)
def test_a_normalized_graph_stays_as_it_is(case: dict[str, Any]) -> None:
    assert ir_normalized(case["normalized"]) == case["normalized"]


@pytest.mark.parametrize("case", CASES, ids=NAMES)
def test_sending_the_normalized_form_stores_the_same_hash(case: dict[str, Any]) -> None:
    """The editor shows a graph normalized, and sending that stores what the raw graph would."""
    assert graph_hash(_stored(case["normalized"])) == graph_hash(_stored(case["graph"]))


@pytest.mark.parametrize("case", CASES, ids=NAMES)
def test_only_a_label_on_a_graph_declared_at_version_1_is_refused(case: dict[str, Any]) -> None:
    stored = _stored(case["graph"])
    codes = {error.code for error in validate_graph(stored)}
    labelled = any("label" in node for node in stored["nodes"])
    declared_one = stored.get("ir_version") == 1 and labelled
    assert ("label_needs_ir_version_2" in codes) == declared_one


def test_the_cases_cover_both_directions_of_the_rule() -> None:
    """A label adds version 2, and a graph declared at version 2 keeps it with no label left."""
    added = [case for case in CASES if "ir_version" not in case["graph"]]
    assert any(case["normalized"].get("ir_version") == 2 for case in added)
    assert any(
        case["graph"].get("ir_version") == 2
        and all("label" not in node for node in case["normalized"]["nodes"])
        for case in CASES
    )
