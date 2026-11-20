"""Renaming a workflow: creation's rule for the name, and the refusals a rename writes (Decision
0037 N2 and N5, US-19.1). The database side runs on a disposable stack."""

import asyncio
from uuid import uuid4

import pytest
from psycopg.errors import UniqueViolation
from pydantic import ValidationError

from autobots.application.sql import SqlParams
from autobots.application.workflows import WorkflowRefused, rename_workflow
from autobots.contracts.workflows import WorkflowCreate, WorkflowRename


class _NoRow:
    async def fetchone(self) -> None:
        return None


class _Connection:
    """Answers the rename's update with `outcome`: an exception to raise, or no row."""

    def __init__(self, outcome: BaseException | None) -> None:
        self.outcome = outcome
        self.statements: list[str] = []

    async def execute(self, statement: str, values: SqlParams | None = None, /) -> _NoRow:
        self.statements.append(statement)
        if self.outcome is not None:
            raise self.outcome
        return _NoRow()


@pytest.mark.parametrize("name", ["", "x" * 101])
def test_a_name_outside_creations_rule_is_refused(name: str) -> None:
    for contract in (WorkflowRename, WorkflowCreate):
        with pytest.raises(ValidationError):
            contract.model_validate({"name": name})


def test_a_name_of_one_to_a_hundred_characters_is_accepted() -> None:
    assert WorkflowRename(name="x" * 100).name == "x" * 100
    assert WorkflowRename(name="Monthly FX note").name == "Monthly FX note"


def test_a_name_the_unique_constraint_refuses_is_workflow_name_taken() -> None:
    connection = _Connection(UniqueViolation("duplicate key value violates unique constraint"))
    with pytest.raises(WorkflowRefused) as refused:
        asyncio.run(rename_workflow(connection, uuid4(), uuid4(), "Taken"))  # type: ignore[arg-type]  # a fake connection
    assert refused.value.code == "workflow_name_taken"
    assert refused.value.kind == "conflict"


def test_another_workspaces_workflow_is_not_found() -> None:
    connection = _Connection(None)
    with pytest.raises(WorkflowRefused) as refused:
        asyncio.run(rename_workflow(connection, uuid4(), uuid4(), "Anything"))  # type: ignore[arg-type]  # a fake connection
    assert refused.value.code == "workflow_not_found"


def test_the_rename_updates_only_the_name() -> None:
    connection = _Connection(None)
    with pytest.raises(WorkflowRefused):
        asyncio.run(rename_workflow(connection, uuid4(), uuid4(), "Anything"))  # type: ignore[arg-type]  # a fake connection
    assert connection.statements == [
        "update public.workflows set name = %s where id = %s and workspace_id = %s returning id"
    ]
