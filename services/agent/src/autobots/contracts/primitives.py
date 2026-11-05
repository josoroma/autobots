"""Boundary-validated values shared by the public contracts."""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field

# Strict, and unknown fields are refused, so a misnamed or private field is an error.
STRICT_CONTRACT = ConfigDict(strict=True, extra="forbid", frozen=True)

# JavaScript cannot represent integers above this exactly, so neither side accepts them.
MAX_SAFE_INTEGER = 9007199254740991

Identifier = UUID

# Exact integer microdollars. Floats and strings are refused by strict validation.
MicroUsd = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
Sequence = Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]


def _in_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be in UTC")
    return value.astimezone(UTC)


UtcTimestamp = Annotated[
    AwareDatetime,
    AfterValidator(_in_utc),
    Field(json_schema_extra={"pattern": r"^.+(Z|[+-]00:00)$"}),
]
