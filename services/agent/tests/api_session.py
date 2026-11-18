"""The identity a test of the API in process signs in with: the internal credential, the session
secret, one workspace and its settings, members with the roles a test names, and session headers
(refactor plan R-66, PTST-11). The API over a fake database is fake_api.py's.
"""

import time
from collections.abc import Mapping
from uuid import UUID

import jwt
from fastapi.testclient import TestClient
from pydantic import SecretStr

from autobots.api.app import create_app
from autobots.api.resources import AppResources
from autobots.api.settings import Settings

INTERNAL = "fixture-internal"
SECRET = "fixture-jwt-secret-with-enough-length"
USER_A = UUID("a1111111-1111-4111-8111-111111111111")
WORKSPACE = UUID("a0000000-0000-4000-8000-000000000001")
SETTINGS = Settings(
    internal_token=SecretStr(INTERNAL),
    jwt_secret=SecretStr(SECRET),
    allowed_hosts=("testserver",),
)


class Members:
    """Members of WORKSPACE with the roles named, so a test's role is a visible argument. Nobody
    else belongs anywhere."""

    def __init__(self, roles: Mapping[UUID, str]) -> None:
        self.roles = dict(roles)

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return user_id in self.roles and workspace_id == WORKSPACE

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [WORKSPACE] if user_id in self.roles else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return self.roles.get(user_id)


class Membership(Members):
    """USER_A owns WORKSPACE."""

    def __init__(self) -> None:
        super().__init__({USER_A: "owner"})


def token(user: UUID = USER_A, secret: str = SECRET, **overrides: object) -> str:
    claims = {"sub": str(user), "aud": "authenticated", "exp": time.time() + 60, **overrides}
    return jwt.encode(claims, secret, algorithm="HS256")


def client() -> TestClient:
    return TestClient(
        create_app(AppResources(SETTINGS, membership=Membership())), raise_server_exceptions=False
    )


def headers(bearer: str | None = None, internal: str = INTERNAL) -> dict[str, str]:
    values = {"X-Autobots-Internal": internal}
    return values if bearer is None else {**values, "Authorization": f"Bearer {bearer}"}


def session_headers(user: UUID) -> dict[str, str]:
    """The internal credential and a session for `user`, valid for a minute."""
    return headers(token(user))
