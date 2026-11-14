"""R-02, PAPI-03: every operation declares the error envelope the service actually sends."""

import json

from autobots.api.openapi_export import openapi_document

ENVELOPE = "#/components/schemas/ErrorResponse"
DECLARED = ("401", "403", "404", "409", "422", "500", "503")


def test_every_operation_declares_the_error_envelope() -> None:
    missing = [
        f"{method.upper()} {path} {status}"
        for path, operations in openapi_document()["paths"].items()
        for method, operation in operations.items()
        for status in DECLARED
        if operation["responses"]
        .get(status, {})
        .get("content", {})
        .get("application/json", {})
        .get("schema", {})
        .get("$ref")
        != ENVELOPE
    ]
    assert missing == []


def test_no_operation_documents_a_validation_body_the_service_never_sends() -> None:
    assert "HTTPValidationError" not in json.dumps(openapi_document())
