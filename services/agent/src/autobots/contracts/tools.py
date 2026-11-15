"""The `calculate` tool's input and output. Each other tool family has its own module: GitHub
(github_tools), run files (file_tools), web, market data, code, browsing and `cronjob`, and the
catalog's public view is tool_catalog (refactor plan R-61, PDOM-11)."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import TOOL_CONTRACT


class CalculateInput(BaseModel):
    model_config = TOOL_CONTRACT

    operation: Literal["sum", "mean", "min", "max"]
    values: list[float] = Field(min_length=1, max_length=1000)


class CalculateOutput(BaseModel):
    model_config = TOOL_CONTRACT

    result: float
