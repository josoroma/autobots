"""Stable, safe error responses. Detail stays on the server, in its private log.

This is the one place a refusal becomes a response (refactor plan R-41, PAPI-05, XERR-07): its kind
gives the status, and its family and code the fixed wording. Routes let refusals propagate, and
catch one only to give it a route's own deliberate wording, through `reworded`.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from autobots.application.approvals import ApprovalRefused
from autobots.application.artifacts import ArtifactUnavailable
from autobots.application.credentials.store import CredentialMissing, CredentialStorageUnavailable
from autobots.application.experts import ExpertRefused
from autobots.application.improvements import ImprovementRefused
from autobots.application.memory import MemoryRefused
from autobots.application.provider_settings import (
    EnvironmentManaged,
    InvalidKey,
    StaleVersion,
    ValidationUnavailable,
)
from autobots.application.reconciliation import ReconciliationRefused
from autobots.application.routines import RoutineRefused
from autobots.application.run_admission import AdmissionRefused, ModelNotReady
from autobots.application.run_projection import InvalidCursor
from autobots.application.runs import IdempotencyConflict, LinkRefused, RunNotFound, VersionConflict
from autobots.application.tool_catalog import ToolsUnavailable
from autobots.application.workflows import WorkflowRefused
from autobots.contracts.runs import ErrorResponse
from autobots.domain.budgets import BudgetRefused
from autobots.domain.errors import Refusal, RefusalKind
from autobots.domain.models import NOT_OFFERED_CODE, NOT_OFFERED_MESSAGE, ProfileNotOffered
from autobots.domain.runs import CommandRefused
from autobots.logs import log_event

logger = logging.getLogger("autobots.api")
# psycopg's OperationalError also covers a pool timeout and transaction conflicts such as a
# deadlock, so the wording asks for a retry without claiming an outage (XERR-06).
DATABASE_RETRY = "The database couldn't complete this request. Try again."

# R-02, PAPI-03: every operation declares the body its refusals carry. Declaring 422 replaces
# FastAPI's default validation schema, which this service never sends.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (401, "Not signed in, or not authorized."),
        (403, "Refused for this workspace or role."),
        (404, "Not found."),
        (409, "Conflicts with the current state."),
        (422, "The request is not valid."),
        (500, "Something went wrong."),
        (503, "A required local service isn't ready."),
    )
}


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


STATUS: Final[Mapping[RefusalKind, int]] = MappingProxyType(
    {
        RefusalKind.NOT_FOUND: 404,
        RefusalKind.CONFLICT: 409,
        RefusalKind.INVALID: 422,
        RefusalKind.FORBIDDEN: 403,
        RefusalKind.UNAVAILABLE: 503,
    }
)
# What a refusal no family words says: the description its status declares above.
DEFAULT_WORDING: Final[Mapping[RefusalKind, str]] = MappingProxyType(
    {kind: ERROR_RESPONSES[status]["description"] for kind, status in STATUS.items()}
)


@dataclass(frozen=True)
class Wording:
    """A refusal family's fixed messages: for a code where one is deliberate, else for its kind,
    else one for the whole family."""

    text: str | None = None
    kinds: Mapping[RefusalKind, str] = field(default_factory=dict)
    codes: Mapping[str, str] = field(default_factory=dict)


SAVED_CONFLICT = "That conflicts with what is saved. Reload and try again."
# Each family's wording, found by the refusal's class or its nearest base. Every message is fixed
# server text, so nothing submitted is echoed.
WORDING: Final[Mapping[type, Wording]] = MappingProxyType(
    {
        AdmissionRefused: Wording(
            codes={
                "session_required": "An Expert is chosen through a session.",
                "budget_conflict": "Choose a budget or a limit, not both.",
                "owner_required": "Only an owner can choose an Expert version.",
            }
        ),
        # A goal run's and a workflow execution's alike (Decision 0022 D11).
        BudgetRefused: Wording(
            codes={
                "budget_out_of_range": "Choose a budget from US$0.25 to US$5.00.",
                "budget_off_step": "Choose a budget in steps of US$0.25.",
                "budget_above_daily_cap": (
                    "That budget is more than what's left of today's spending cap."
                ),
            }
        ),
        ModelNotReady: Wording("Model-backed work needs a usable OpenRouter key."),
        ToolsUnavailable: Wording(
            "A tool this Expert grants is unavailable in this install. See Tools for what it needs."
        ),
        IdempotencyConflict: Wording("This key was already used with different content."),
        VersionConflict: Wording("The run changed. Reload and try again."),
        LinkRefused: Wording(
            "Only a finished goal run of its own, in this workspace, can be continued."
        ),
        RunNotFound: Wording("That run is not available."),
        CommandRefused: Wording("That is not allowed in the run's current state."),
        InvalidCursor: Wording("That page cursor is not valid."),
        ReconciliationRefused: Wording("That can't be recorded."),
        ApprovalRefused: Wording("That decision can't be applied."),
        ArtifactUnavailable: Wording("That artifact is not available."),
        ImprovementRefused: Wording("That can't be done to this proposal."),
        MemoryRefused: Wording(codes={"expert_not_found": "That Expert isn't in this workspace."}),
        ExpertRefused: Wording(
            kinds={
                RefusalKind.NOT_FOUND: "That is not available.",
                RefusalKind.CONFLICT: SAVED_CONFLICT,
                RefusalKind.INVALID: "That configuration is not allowed.",
            }
        ),
        RoutineRefused: Wording(
            kinds={
                RefusalKind.NOT_FOUND: "That is not available.",
                RefusalKind.CONFLICT: SAVED_CONFLICT,
                RefusalKind.INVALID: "That routine isn't valid.",
            },
            codes={"draft_not_runnable": "A routine binds a published version, not a draft."},
        ),
        WorkflowRefused: Wording(
            kinds={
                RefusalKind.NOT_FOUND: "That workflow is not available.",
                RefusalKind.CONFLICT: SAVED_CONFLICT,
            },
            codes={
                "workflow_draft_not_found": "This workflow has no saved draft.",
                "workflow_version_conflict": (
                    "A newer version was published. Reload and try again."
                ),
            },
        ),
        StaleVersion: Wording("The settings changed. Reload and try again."),
        EnvironmentManaged: Wording("The environment supplies this key. Change it there."),
        InvalidKey: Wording("That key was not accepted. The previous key is unchanged."),
        ValidationUnavailable: Wording("The key could not be checked right now. Nothing changed."),
        CredentialStorageUnavailable: Wording("Credential storage is unavailable."),
        CredentialMissing: Wording("No credential is configured."),
    }
)


def refusal_message(refusal: Refusal) -> str:
    """The fixed wording for `refusal`. A profile's reason and a graph's error codes are server
    values, the only text a message is built from."""
    if isinstance(refusal, ProfileNotOffered):
        return refusal.reason
    if isinstance(refusal, WorkflowRefused) and refusal.kind is RefusalKind.INVALID:
        return f"That isn't valid: {', '.join(sorted({item.code for item in refusal.errors}))}."
    if isinstance(refusal, WorkflowRefused) and refusal.code == NOT_OFFERED_CODE:
        return refusal.reason or NOT_OFFERED_MESSAGE
    wording = next(
        (WORDING[family] for family in type(refusal).__mro__ if family in WORDING), Wording()
    )
    return (
        wording.codes.get(refusal.code)
        or wording.kinds.get(refusal.kind)
        or wording.text
        or DEFAULT_WORDING[refusal.kind]
    )


def reworded(refusal: Refusal, message: str, *, code: str | None = None) -> ApiError:
    """`refusal` at its kind's status, in a route's own deliberate wording, and its own code where
    a route names what was refused."""
    return ApiError(STATUS[refusal.kind], code or refusal.code, message)


def _response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(code=code, message=message).model_dump()
    return JSONResponse(status_code=status_code, content=body)


def _log(level: int, event: str, request: Request, error: Exception) -> None:
    """The method and the matched route's template, never the path, which holds whole IDs."""
    route = getattr(request.scope.get("route"), "path", None)
    fields = {
        "method": request.method,
        "route": route if isinstance(route, str) else "unmatched",
        "error": error,
    }
    log_event(logger, event, level, **fields)


def transient(error: psycopg.OperationalError) -> bool:
    """Whether a retry can succeed: a lost or refused connection (no SQLSTATE, or class 08), a pool
    wait that ran out, a serialization conflict or deadlock (class 40), or a server shutting down
    (57P0x). A full disk (class 53), a program limit (54) or a cancelled statement can't."""
    state = error.sqlstate
    return state is None or state.startswith(("08", "40", "57P0"))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def api_error(_request: Request, error: ApiError) -> JSONResponse:
        return _response(error.status_code, error.code, error.message)

    @app.exception_handler(Refusal)
    async def refused(_request: Request, error: Refusal) -> JSONResponse:
        # A refusal is an answer, not a failure, so it isn't logged; its detail stays internal.
        return _response(STATUS[error.kind], error.code, refusal_message(error))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError) -> JSONResponse:
        # The rejected input is not echoed.
        return _response(422, "invalid_request", "The request is not valid.")

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        return _response(error.status_code, "request_failed", "The request failed.")

    @app.exception_handler(psycopg.OperationalError)
    async def database_unavailable(request: Request, error: Exception) -> JSONResponse:
        if isinstance(error, psycopg.OperationalError) and not transient(error):
            # A full disk or a program limit won't clear on a retry, so it isn't offered one.
            _log(logging.ERROR, "api.unhandled", request, error)
            return _response(500, "internal_error", "Something went wrong.")
        # The code the no-pool path answers with, so a person is offered a retry (XERR-06).
        _log(logging.WARNING, "api.database_unavailable", request, error)
        return _response(503, "service_unavailable", DATABASE_RETRY)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, error: Exception) -> JSONResponse:
        # Starlette raises the error again after this, and uvicorn's own line adds no route.
        _log(logging.ERROR, "api.unhandled", request, error)
        return _response(500, "internal_error", "Something went wrong.")
