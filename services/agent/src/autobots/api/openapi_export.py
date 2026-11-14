"""Print the OpenAPI document. Builds the pure application and opens nothing.

It lives in api/ because it builds the app; contracts/ imports no other layer (STD-01).
"""

import json
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from autobots.api.app import create_app
from autobots.contracts.models import EffectiveRolePolicy
from autobots.contracts.runs import ErrorResponse, RunEvent, RunSummary

# Public models not yet referenced by a route still belong in the contract.
PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    RunSummary,
    RunEvent,
    ErrorResponse,
    EffectiveRolePolicy,
)


def openapi_document() -> dict[str, Any]:
    document = create_app().openapi()
    _, schemas = models_json_schema(
        [(model, "validation") for model in PUBLIC_MODELS],
        ref_template="#/components/schemas/{model}",
    )
    components = document.setdefault("components", {}).setdefault("schemas", {})
    components.update(schemas["$defs"])
    return document


def main() -> None:
    print(json.dumps(openapi_document(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
