"""Who may call the Python API. Loopback does not authorize anything."""

import hmac
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, Request

from autobots.api.errors import ApiError
from autobots.api.resources import app_resources
from autobots.api.settings import Settings


def app_settings(request: Request) -> Settings:
    return app_resources(request).settings


def require_internal(
    settings: Annotated[Settings, Depends(app_settings)],
    x_autobots_internal: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.internal_token.get_secret_value()
    supplied = x_autobots_internal or ""
    if not expected or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise ApiError(401, "unauthorized", "This request is not authorized.")


def verified_claims(
    settings: Annotated[Settings, Depends(app_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """The session token's claims, verified once per request: FastAPI caches a dependency's answer
    for the request, so `current_user` and `session_email` read the same decode (PAPI-16)."""
    secret = settings.jwt_secret.get_secret_value()
    scheme, _, token = (authorization or "").partition(" ")
    if not secret or scheme.lower() != "bearer" or not token:
        raise ApiError(401, "unauthorized", "This request is not authorized.")
    try:
        claims: dict[str, object] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub", "aud"]},
        )
    except (jwt.InvalidTokenError, ValueError) as error:
        raise ApiError(401, "unauthorized", "This request is not authorized.") from error
    return claims


Claims = Annotated[dict[str, object], Depends(verified_claims)]


def current_user(claims: Claims) -> UUID:
    """A verified session subject. A browser-supplied user or workspace id is never trusted."""
    try:
        # PyJWT has already refused a subject that isn't a string.
        return UUID(str(claims["sub"]))
    except ValueError as error:
        raise ApiError(401, "unauthorized", "This request is not authorized.") from error


def session_email(_user: Annotated[UUID, Depends(current_user)], claims: Claims) -> str | None:
    """The verified session's own email claim, after `current_user` accepted the token."""
    email = claims.get("email")
    return email if isinstance(email, str) and email else None
