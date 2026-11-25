"""Expert, session and routing contracts, PRD 8.2 and 11.2."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from autobots.contracts.primitives import LAX_CONTRACT, Identifier, UtcTimestamp, Version
from autobots.contracts.tool_catalog import ToolGroupName
from autobots.contracts.tool_fields import DomainName
from autobots.domain.browsing import BrowserKind
from autobots.domain.models import ModelProfileId
from autobots.domain.tool_catalog import ToolGroup


class ExpertConfig(BaseModel):
    # Not strict, so JSON strings become enums. Unknown fields and values are still refused.

    model_config = LAX_CONTRACT

    purpose: str = Field(default="", max_length=1000)
    instructions: str = Field(default="", max_length=20000)
    tools: list[str] = Field(default_factory=list, max_length=20)
    # Groups granted whole, PRD-Tool-Catalog TC-06. Saving expands them into `tools`, so a saved
    # version names explicit tools, and this keeps where they came from for display. The bound is
    # the vocabulary's size, so a new group raises it (PDOM-06).
    tool_groups: list[ToolGroupName] = Field(default_factory=list, max_length=len(ToolGroup))
    skills: list[str] = Field(default_factory=list, max_length=50)
    role_bindings: dict[str, ModelProfileId] = Field(default_factory=dict)
    # Decision 0035 Y3: where a `browse_goal` call of this Expert may go while YOLO is on. The
    # cap is a call's own `allowed_domains` cap. Left out while empty, so a request or receipt
    # without it keeps the bytes it always had (XDUP-04).
    browse_domains: list[DomainName] = Field(
        default_factory=list, max_length=10, exclude_if=lambda domains: not domains
    )
    # Decision 0038 Z1: the browser a `browse_goal` call of this Expert drives. Left out while it is
    # the default, for the same reason.
    browser: BrowserKind = Field(default="box", exclude_if=lambda browser: browser == "box")

    @field_validator("browse_domains")
    @classmethod
    def _once_each(cls, domains: list[str]) -> list[str]:
        if len(set(domains)) != len(domains):
            raise ValueError("browse_domains repeats a domain")
        return domains


class ExpertCreate(BaseModel):
    model_config = LAX_CONTRACT

    name: str = Field(min_length=1, max_length=100)
    config: ExpertConfig


class ExpertRevision(BaseModel):
    model_config = LAX_CONTRACT

    expected_version: Version
    config: ExpertConfig


# Read from the version's stored record (persistence/records.py, refactor plan R-52).
class ExpertConfigView(BaseModel):
    """A saved version as stored. It has no request limits, since tool groups can expand a saved
    version past one."""

    model_config = LAX_CONTRACT

    # ExpertConfig's defaults, so the generated client types both alike.
    purpose: str = ""
    instructions: str = ""
    tools: list[str] = Field(default_factory=list)
    tool_groups: list[ToolGroupName] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    role_bindings: dict[str, ModelProfileId] = Field(default_factory=dict)
    browse_domains: list[str] = Field(default_factory=list, exclude_if=lambda domains: not domains)
    browser: BrowserKind = Field(default="box", exclude_if=lambda browser: browser == "box")


class ExpertVersionView(BaseModel):
    model_config = LAX_CONTRACT

    version: int
    config: ExpertConfigView


class ExpertView(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    id: Identifier
    name: str
    latest_version: int
    versions: list[ExpertVersionView]
    # PRD-Studio EX-01: runs started with this Expert in this workspace, and the newest one's start.
    run_count: int
    last_run_at: UtcTimestamp | None


class ExpertList(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    experts: list[ExpertView]


class SessionExpert(BaseModel):
    model_config = LAX_CONTRACT

    expert_id: Identifier
    version: Version | None = None


class SessionCreate(BaseModel):
    model_config = LAX_CONTRACT

    kind: Literal["direct", "coordinator"]
    experts: list[SessionExpert] = Field(min_length=1, max_length=20)


class RouteOption(BaseModel):
    """What a user sees before starting work. Nothing beyond this is granted."""

    model_config = LAX_CONTRACT

    expert_id: Identifier
    name: str
    version: int
    purpose: str
    tools: list[str]
    role_bindings: dict[str, str]


class SessionView(BaseModel):
    model_config = LAX_CONTRACT

    schema_version: Literal[1]
    id: Identifier
    kind: Literal["direct", "coordinator"]
    options: list[RouteOption]
