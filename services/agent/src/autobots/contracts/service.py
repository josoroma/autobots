"""Contracts for the first routes."""

from typing import Literal

from pydantic import BaseModel

from autobots.contracts.primitives import STRICT_CONTRACT, Identifier


class ServiceHealth(BaseModel):
    """Liveness only. Holds no address, version or secret."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    status: Literal["ok"]


class WorkspaceSummary(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    id: Identifier
