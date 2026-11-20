"""A browse's steps as the run's tool row shows them, Decision 0035 Y11 and US-17.4.

Each browser-use step keeps one screenshot for people, never for a model (Y16), with the page it
ended on and the forms it submitted, each as host and path only. The screenshot itself is a
separate, authorized download.
"""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import STRICT_CONTRACT


class BrowseStep(BaseModel):
    model_config = STRICT_CONTRACT

    step: int = Field(ge=1)
    page: str | None = Field(default=None, description="The page it ended on, as host and path.")
    submits: list[str] = Field(description="Each form it submitted, as host and path.")
    screenshot: bool = Field(description="Whether a screenshot was kept for this step.")


class BrowseStepList(BaseModel):
    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    steps: list[BrowseStep]
