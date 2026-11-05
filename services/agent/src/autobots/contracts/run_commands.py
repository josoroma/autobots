"""Requests and responses for run admission and commands."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from autobots.contracts.primitives import STRICT_CONTRACT, Identifier, MicroUsd
from autobots.domain.runs import RunStatus


class RunRequest(BaseModel):
    model_config = STRICT_CONTRACT

    goal_text: str = Field(min_length=1, max_length=20000)
    limit_micro_usd: MicroUsd = 1_000_000


class RunAccepted(BaseModel):
    """Not strict, since it is built from database values. It is validated as it is built."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    run_id: Identifier
    version: int
    status: RunStatus
    replayed: bool


class RunCommandRequest(BaseModel):
    model_config = STRICT_CONTRACT

    expected_version: int = Field(ge=1)


class RunCommandResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1]
    run_id: Identifier
    version: int
    status: RunStatus
    changed: bool
