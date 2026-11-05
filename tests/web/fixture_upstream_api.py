"""The real configured API and database with a fake OpenRouter, for qualification only. Not a product path.

The fake logs every upstream request, so a run can show that only key metadata and the catalog were used.
Keys starting `sk-or-valid` pass, `sk-or-reject` get 401, and anything starting `sk-or-down` cannot connect.
"""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import sys

import httpx
import uvicorn

from autobots.adapters.models.factory import OPENROUTER_BASE_URL
from autobots.adapters.models.openrouter_metadata import catalog_fetcher, key_validator
from autobots.api.main import create_configured_app
from autobots.domain.models import PROFILES

LOG = Path(os.environ['AUTOBOTS_TEST_UPSTREAM_LOG'])


def handle(request: httpx.Request) -> httpx.Response:
    with LOG.open('a') as log:
        log.write(f'{request.method} {request.url.path}\n')
    if request.url.path.endswith('/key'):
        token = request.headers.get('authorization', '').removeprefix('Bearer ')
        if token.startswith('sk-or-down'):
            raise httpx.ConnectError('arranged outage')
        return httpx.Response(200 if token.startswith('sk-or-valid') else 401, json={'data': {}})
    if request.url.path.endswith('/models'):
        if Path(os.environ['AUTOBOTS_TEST_CATALOG_DOWN']).exists():
            return httpx.Response(503)
        data = [{'id': p.wire_id, 'canonical_slug': p.canonical_id, 'supported_parameters': []} for p in PROFILES.values()]
        return httpx.Response(200, content=json.dumps({'data': data}))
    return httpx.Response(599)


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=OPENROUTER_BASE_URL, transport=httpx.MockTransport(handle))


def main() -> None:
    app = create_configured_app()
    app.state.provider_context = _with_fake(app.state.provider_context)
    uvicorn.run(app, host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')


def _with_fake(context):  # type: ignore[no-untyped-def]
    return replace(context, validate_key=key_validator(make_client), fetch_catalog=catalog_fetcher(make_client))


if __name__ == '__main__':
    main()
