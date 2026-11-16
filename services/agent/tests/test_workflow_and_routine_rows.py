"""Workflow and routine rows map field by field (refactor plan R-54, XTYP-04, PPRD-12).

A published version, a node instance, an emission and a routine occurrence each take every view
field from the row field of its own meaning. Every value differs, so a swap fails, and an unknown
stored source or status raises instead of reaching a client.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest

from autobots.application.routines import occurrence_view
from autobots.application.sql import UnknownStoredValue
from autobots.application.workflow_executions import emission_view, instance_state, instance_view
from autobots.application.workflows import version_view
from autobots.persistence.rows import (
    EmissionRow,
    NodeInstanceRow,
    OccurrenceRow,
    WorkflowVersionRow,
)

GRAPH: dict[str, Any] = {"nodes": [], "links": []}
RUN = UUID(int=9)


def test_a_published_version_takes_each_field_from_its_own_column() -> None:
    row = WorkflowVersionRow(
        workflow_id=RUN,
        version=3,
        graph_hash="h" * 64,
        source="model_proposal",
        graph=GRAPH,
        block_versions={"agent": "2"},
    )
    view = version_view(row)
    assert (view.version, view.graph_hash, view.source, view.block_versions) == (
        3,
        "h" * 64,
        "model_proposal",
        {"agent": "2"},
    )
    assert (view.graph.nodes, view.graph.links) == ([], [])
    with pytest.raises(UnknownStoredValue, match="import"):
        version_view(replace(row, source="import"))


def test_an_instance_and_an_emission_take_their_own_columns() -> None:
    instance = instance_view(
        instance_state(
            NodeInstanceRow(
                instance_key="each#2", node_id="each", iteration=2, status="failed", error_code="e1"
            )
        )
    )
    assert (instance.key, instance.node_id, instance.iteration) == ("each#2", "each", 2)
    assert (instance.status, instance.error_code) == ("failed", "e1")
    emission = emission_view(
        EmissionRow(instance_key="each#2", port="out", sequence=4, value='"sk-or-v1-abc123def456"')
    )
    assert (emission.instance_key, emission.port, emission.sequence) == ("each#2", "out", 4)
    assert "sk-or-v1-abc123def456" not in emission.value


def test_an_occurrence_takes_its_own_columns_in_utc() -> None:
    local = datetime(2026, 11, 15, 3, tzinfo=timezone(timedelta(hours=-6)))
    row = OccurrenceRow(
        occurrence_time=local, routine_version=5, status="blocked", reason="key_missing", run_id=RUN
    )
    view = occurrence_view(row)
    assert (view.occurrence_time, view.routine_version) == (local.astimezone(UTC), 5)
    assert (view.status, view.reason, view.run_id) == ("blocked", "key_missing", RUN)
    with pytest.raises(UnknownStoredValue, match="queued"):
        occurrence_view(replace(row, status="queued"))
