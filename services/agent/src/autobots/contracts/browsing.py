"""`browse_goal`'s input and output, PRD-Tool-Catalog "Autonomous browsing", Decision 0020 and
Decision 0035 Y9.

Ceilings are in the schema, so a call past one is refused before any approval, container or model
call. Nothing here carries a credential (PK-01). The start URL must already be inside the call's
own domains, so the first navigation can't be the one that leaves them.
"""

import json
import re
from typing import Literal
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, SchemaError  # type: ignore[import-untyped]  # jsonschema ships no stubs
from pydantic import BaseModel, Field, JsonValue, model_validator

from autobots.contracts.primitives import TOOL_CONTRACT
from autobots.contracts.tool_fields import DomainName
from autobots.contracts.web_tools import WebOutput

Stopped = Literal[
    "done", "max_steps", "max_seconds", "refused_action", "invalid_action", "cancelled"
]
# Decision 0035 Y19: an output schema's size, and the form of a link field's path, such as
# `flights[].url`, where `[]` steps into an array.
OUTPUT_SCHEMA_BYTES = 8192
LINK_FIELDS = 20
LINK_FIELD = re.compile(
    r"^(\[\]|[A-Za-z_][A-Za-z0-9_-]*(\[\])?)(\.[A-Za-z_][A-Za-z0-9_-]*(\[\])?)*$"
)
# Version 3 adds `bot_check` (Decision 0035 Y10).
StoppedV3 = Literal[
    "done",
    "max_steps",
    "max_seconds",
    "refused_action",
    "invalid_action",
    "cancelled",
    "bot_check",
]


def within(host: str, domains: list[str]) -> bool:
    """A host is inside a domain when it is that domain or one of its subdomains."""
    name = host.lower().rstrip(".")
    return any(name == domain or name.endswith("." + domain) for domain in domains)


class _BrowseGoal(BaseModel):
    """What both versions take, and the check that keeps the start URL inside the domains."""

    model_config = TOOL_CONTRACT

    task: str = Field(min_length=1, max_length=2000)
    start_url: str = Field(min_length=9, max_length=2048)
    allowed_domains: list[DomainName] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def _inside(self) -> "_BrowseGoal":
        if len(set(self.allowed_domains)) != len(self.allowed_domains):
            raise ValueError("allowed_domains repeats a domain")
        parts = urlsplit(self.start_url)
        if parts.scheme != "https" or parts.username or parts.password or not parts.hostname:
            raise ValueError("start_url must be a plain https URL")
        if not within(parts.hostname, self.allowed_domains):
            raise ValueError("start_url must be inside allowed_domains")
        return self


# Version 1: the read-only loop's limits (Decision 0020). A comment, since a docstring would enter
# the published schema.
class BrowseGoalInput(_BrowseGoal):
    max_steps: int = Field(default=10, ge=1, le=20)
    max_seconds: int = Field(default=120, ge=10, le=300)


# Version 2, Decision 0035 Y9: up to browser-use's limits, each optional. An unnamed limit is the
# engine's own default, and the loop caps any limit at its own.
class BrowseGoalV2Input(_BrowseGoal):
    max_steps: int | None = Field(default=None, ge=1, le=40)
    max_seconds: int | None = Field(default=None, ge=10, le=600)


class BrowseGoalOutput(WebOutput):
    summary: str
    visited: list[str]
    visited_count: int
    steps: int
    model_calls: int
    stopped: Stopped


# Version 3, Decision 0035 Y12 and Y19: an optional output schema, a JSON Schema (Draft 2020-12)
# object of at most 8 KB whose top-level `x-link-fields` lists the paths of its link fields.
class BrowseGoalV3Input(BrowseGoalV2Input):
    output_schema: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def _schema(self) -> "BrowseGoalV3Input":
        schema = self.output_schema
        if schema is None:
            return self
        if len(json.dumps(schema).encode()) > OUTPUT_SCHEMA_BYTES:
            raise ValueError("output_schema is larger than 8 KB")
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            raise ValueError("output_schema isn't a JSON Schema") from None
        links = schema.get("x-link-fields", [])
        if not isinstance(links, list) or len(links) > LINK_FIELDS:
            raise ValueError("x-link-fields must be a list of at most 20 paths")
        if any(not isinstance(link, str) or not LINK_FIELD.match(link) for link in links):
            raise ValueError("an x-link-fields entry isn't a path such as flights[].url")
        return self


# Version 3's output: the typed result, each submit's host and path, and `bot_check`.
class BrowseGoalV3Output(WebOutput):
    summary: str
    visited: list[str]
    visited_count: int
    steps: int
    model_calls: int
    stopped: StoppedV3
    submits: list[str] = Field(default_factory=list)
    result: JsonValue = None
