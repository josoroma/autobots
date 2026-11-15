"""Boundary-validated values, and the three model configurations every public contract uses.

Strictness is chosen per value, not per model (DH-06, refactor plan R-61, PDOM-05): money, counts,
versions and flags refuse a string, a float or a boolean in any model, and `Strict()` leaves the
JSON Schema as it was. A lax model still reads a UUID, an enum or a timestamp from its JSON string,
since FastAPI validates a request body as Python values.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, ConfigDict, Field, Strict, StrictBool

# Strict, and unknown fields are refused, so a misnamed or private field is an error. Each value
# must already have its type, so a request body uses it only when every field is a JSON string,
# number or boolean, as RunCommandRequest's is. A body with a UUID, enum or timestamp is lax.
STRICT_CONTRACT = ConfigDict(strict=True, extra="forbid", frozen=True)
# Unknown fields are refused, and a JSON string becomes a UUID, an enum or a timestamp. Request
# bodies and views built from rows use it, and the strict values below keep their own rule.
LAX_CONTRACT = ConfigDict(extra="forbid", frozen=True)
# A tool's input or output: lax, as a model's arguments arrive as JSON, and never NaN or infinite.
TOOL_CONTRACT = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

# JavaScript cannot represent integers above this exactly, so neither side accepts them.
MAX_SAFE_INTEGER = 9007199254740991
# The most text one run file holds, in characters (US-14.9).
MAX_FILE_CHARACTERS = 256_000

Identifier = UUID

# Exact integer microdollars. A float, a string or a boolean is refused in any model.
MicroUsd = Annotated[int, Strict(), Field(ge=0, le=MAX_SAFE_INTEGER)]
# How many of something, or a version a request expects where 0 means none yet: a JSON integer.
Count = Annotated[int, Strict(), Field(ge=0)]
# A version a request names or expects, from 1: a JSON integer.
Version = Annotated[int, Strict(), Field(ge=1)]
# A JSON boolean. Lax validation would read "no", "off" or 0 as false.
Flag = StrictBool
# A run event's place in its run, from 1.
EventSequence = Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]


def _in_utc(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be in UTC")
    return value.astimezone(UTC)


UtcTimestamp = Annotated[
    AwareDatetime,
    AfterValidator(_in_utc),
    Field(json_schema_extra={"pattern": r"^.+(Z|[+-]00:00)$"}),
]


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


# A timestamp a model sends, held in UTC (DH-06): one without an offset, such as a date alone, is
# UTC, and one with an offset is the same instant. Its schema stays `date-time`, so a tool input
# that takes it publishes the schema it always did (Decision 0029 F13, PADP-17, PDOM-03).
UtcInput = Annotated[datetime, AfterValidator(_as_utc)]
