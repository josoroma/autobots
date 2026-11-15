"""Each contract vocabulary equals the source that owns it (refactor plan R-61, PDOM-04, PDOM-06,
XERR-08).

A Literal in a contract mirrors a domain enum or a column's check constraint. Strict descriptors
take the catalog's strings, so the contracts keep Literals, and these tests hold each one equal to
its owner, so a new value fails here, not as a validation error on the screen that first shows it.
A tightened response field takes only values a check constraint or the application allows; one
whose stored history may hold others stays `str`.
"""

import re
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import Any, get_args

import pytest

from autobots.api.openapi_export import openapi_document
from autobots.application.model_admission import InvocationStatus
from autobots.contracts.approvals import ApprovalResult, ApprovalView, PolicyRuleName
from autobots.contracts.experts import ExpertConfig
from autobots.contracts.improvements import CandidateStatus, KnowledgeKind
from autobots.contracts.operations import DelayedOccurrence
from autobots.contracts.routines import OccurrenceStatus
from autobots.contracts.run_workspace import (
    BindingSourceName,
    ModelCallStatus,
    ReceiptStatusName,
    RunListItem,
    RunWorkspace,
)
from autobots.contracts.runs import ToolOutcomeName
from autobots.contracts.tool_catalog import (
    AvailabilityName,
    CostClassName,
    GrantSiteName,
    OperationClassName,
    SideEffectName,
    ToolGroupName,
    ToolProviderName,
)
from autobots.contracts.workflows import ExecutionView, WorkflowSource
from autobots.domain.effects import ApprovalStatus, ReceiptStatus
from autobots.domain.models import BindingSource
from autobots.domain.runs import RunStatus
from autobots.domain.stops import StopCode
from autobots.domain.tool_catalog import (
    CostClass,
    GrantSite,
    SideEffect,
    ToolAvailability,
    ToolGroup,
    ToolProvider,
)
from autobots.domain.tools import OperationClass, ToolOutcome

MIGRATIONS = Path(__file__).resolve().parents[3] / "supabase/migrations"


def values(literal: Any) -> set[str]:  # noqa: ANN401 - a typing.Literal, which has no static type
    return {str(item) for item in get_args(literal)}


@pytest.mark.parametrize(
    ("literal", "enum"),
    [
        (ToolGroupName, ToolGroup),
        (ToolProviderName, ToolProvider),
        (OperationClassName, OperationClass),
        (AvailabilityName, ToolAvailability),
        (GrantSiteName, GrantSite),
        (SideEffectName, SideEffect),
        (CostClassName, CostClass),
        (ToolOutcomeName, ToolOutcome),
        (BindingSourceName, BindingSource),
        (ReceiptStatusName, ReceiptStatus),
        (ModelCallStatus, InvocationStatus),
    ],
    ids=lambda item: getattr(item, "__name__", None) or "literal",
)
def test_each_contract_literal_equals_its_domain_enum(
    literal: Any,  # noqa: ANN401 - a typing.Literal, which has no static type
    enum: type[StrEnum],
) -> None:
    assert values(literal) == {member.value for member in enum}


@cache
def check_constraint(table: str, column: str) -> set[str]:
    """The values a text column's check constraint allows, as the migrations leave it: its table's
    definition, then any later `alter table` that adds the constraint again."""
    allowed: set[str] | None = None
    # A nullable column's constraint reads `check (column is null or column in (...))`.
    listed = rf"check\s*\(\s*(?:{column}\s+is\s+null\s+or\s+)?{column}\s+in\s*\(([^)]*)\)\s*\)"
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        text = migration.read_text()
        created = re.search(
            rf"create table (?:\w+\.)?{table} \((.*?)\n\);", text, flags=re.DOTALL | re.IGNORECASE
        )
        if created:
            found = re.search(rf"\b{column}\s+text\b[^,]*?{listed}", created[1], flags=re.DOTALL)
            if found:
                allowed = set(re.findall(r"'([^']*)'", found[1]))
        for altered in re.finditer(
            rf"alter table (?:\w+\.)?{table}\b[^;]*?{listed}", text, flags=re.DOTALL | re.IGNORECASE
        ):
            allowed = set(re.findall(r"'([^']*)'", altered[1]))
    assert allowed is not None, f"no check constraint on {table}.{column}"
    return allowed


@pytest.mark.parametrize(
    ("allowed", "table", "column"),
    [
        ({status.value for status in RunStatus}, "runs", "status"),
        ({status.value for status in ApprovalStatus}, "approval_requests", "status"),
        (values(OccurrenceStatus), "routine_occurrences", "status"),
        (values(ModelCallStatus), "model_invocations", "status"),
        (values(ReceiptStatusName), "tool_receipts", "status"),
        (values(CandidateStatus), "improvement_candidates", "status"),
        (values(KnowledgeKind), "improvement_candidates", "kind"),
        (values(KnowledgeKind), "knowledge_versions", "kind"),
        (values(WorkflowSource), "workflow_versions", "source"),
        (values(PolicyRuleName), "approval_requests", "policy_rule"),
    ],
    ids=lambda item: item if isinstance(item, str) else "",
)
def test_each_response_vocabulary_equals_its_check_constraint(
    allowed: set[str], table: str, column: str
) -> None:
    assert allowed == check_constraint(table, column)


def test_the_delayed_occurrences_are_occurrences_that_did_not_run() -> None:
    delayed = values(DelayedOccurrence.model_fields["status"].annotation)
    assert delayed == values(OccurrenceStatus) - {"admitted"}


def test_an_expert_can_name_every_tool_group_and_no_more() -> None:
    assert ExpertConfig(tool_groups=list(ToolGroup)).tool_groups == list(ToolGroup)
    bound = ExpertConfig.model_json_schema()["properties"]["tool_groups"]["maxItems"]
    assert bound == len(ToolGroup)


def test_an_approval_reads_its_stored_status_into_the_shared_enum() -> None:
    assert ApprovalView.model_fields["status"].annotation is ApprovalStatus
    assert ApprovalResult.model_fields["status"].annotation is ApprovalStatus


def test_the_stop_codes_are_published_and_a_stop_reason_stays_open() -> None:
    """XERR-08: the client gets every StopCode as a union, and a code it doesn't know still reads
    and shows, as the repair-limit family and a retired code do."""
    schemas = openapi_document()["components"]["schemas"]
    assert set(schemas["StopCode"]["enum"]) == {code.value for code in StopCode}
    for name in ("RunWorkspace", "RunListItem", "ExecutionView"):
        options = schemas[name]["properties"]["stop_reason"]["anyOf"]
        assert {"$ref": "#/components/schemas/StopCode"} in options
        assert {"type": "string"} in options
    for model in (RunWorkspace, RunListItem, ExecutionView):
        annotation = model.model_fields["stop_reason"].annotation
        assert StopCode in get_args(annotation) and str in get_args(annotation)
