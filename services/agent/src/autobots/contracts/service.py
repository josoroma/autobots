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


class SessionWorkspace(BaseModel):
    """A workspace the session belongs to, with its name and the session's role in it."""

    model_config = STRICT_CONTRACT

    id: Identifier
    name: str
    role: Literal["owner", "member"]


class SessionSummary(BaseModel):
    """Who the verified session is, and the workspaces membership grants it.

    `display_name` is the saved profile name, else the local part of the session's email, else
    "Member" (PRD-Studio ID-01). `email` is the session's own address and is never another user's.
    """

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    user_id: Identifier
    workspace_ids: list[Identifier]
    display_name: str
    display_name_saved: bool
    email: str | None
    workspaces: list[SessionWorkspace]


class ProfileView(BaseModel):
    """The session's own profile: the shown name, and whether it is saved or a fallback."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    display_name: str
    saved: bool
    email: str | None


class ProfileUpdate(BaseModel):
    """A new display name. The route checks 1 to 60 characters after trimming."""

    model_config = STRICT_CONTRACT

    display_name: str
