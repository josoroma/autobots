"""Who may call the Python API. Loopback does not authorize anything."""

import hmac
from typing import Annotated, Protocol
from uuid import UUID

import jwt
from fastapi import Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.settings import Settings


class MembershipStore(Protocol):
    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool: ...


class DenyAllMembership:
    """The default until real membership is connected: no identity reaches any workspace."""

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return False


def app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def require_internal(
    settings: Annotated[Settings, Depends(app_settings)],
    x_autobots_internal: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.internal_token.get_secret_value()
    supplied = x_autobots_internal or ""
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "This request is not authorized.")


def current_user(
    settings: Annotated[Settings, Depends(app_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    """A verified session subject. A browser-supplied user or workspace id is never trusted."""
    secret = settings.jwt_secret.get_secret_value()
    scheme, _, token = (authorization or "").partition(" ")
    if not secret or scheme.lower() != "bearer" or not token:
        raise ApiError(401, "unauthorized", "This request is not authorized.")
    try:
        claims = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub", "aud"]},
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as error:
        raise ApiError(401, "unauthorized", "This request is not authorized.") from error


async def require_workspace_member(
    workspace_id: UUID,
    request: Request,
    user_id: Annotated[UUID, Depends(current_user)],
) -> UUID:
    store: MembershipStore = request.app.state.membership
    if not await store.is_member(user_id, workspace_id):
        raise ApiError(403, "forbidden", "This workspace is not available.")
    return workspace_id
