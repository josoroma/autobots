"""Stable, safe error responses. Detail stays on the server."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from autobots.contracts.runs import ErrorResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code
        self.message = message


def _response(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(code=code, message=message).model_dump()
    return JSONResponse(status_code=status_code, content=body)


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

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, _error: Exception) -> JSONResponse:
        return _response(500, "internal_error", "Something went wrong.")
