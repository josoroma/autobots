"""A sample public model. The real contract is generated from the product's own models."""

from pydantic import BaseModel


class RunSummary(BaseModel):
    id: str
    status: str
    version: int
