"""Stable, safe error responses. Detail stays on the server, in its private log."""

import logging
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from autobots.contracts.runs import ErrorResponse

# The standard logger, as STD-01 keeps api/ from importing operations/logs.py, whose formatter and
# conventions apply once api/main.py configures logging.
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
    logger.log(level, event, extra={"fields": fields})


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
