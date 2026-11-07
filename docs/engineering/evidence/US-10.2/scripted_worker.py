#!/usr/bin/env python3
"""The product's worker over the fake transport from `tests/db`, with paced calls and full bodies kept. Kept with the evidence.

Nothing leaves this Mac. `[slow]` holds a call open long enough to cancel during it, and `[paced]` spaces the calls so
a stream has events still to come when it's cut. Every request's whole body and non-secret headers are written out for
the scan. Its artifact carries the canary, so a scan that couldn't read stored objects would fail its control.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests/db'))

import product_inference_worker as scripted  # noqa: E402

from autobots.adapters.models.factory import default_sdk_client  # noqa: E402
from autobots.operations.worker import main  # noqa: E402

BODIES = Path(os.environ['AUTOBOTS_TEST_BODIES'])
DELAY = {'[slow]': float(os.environ.get('AUTOBOTS_TEST_SLOW', '4')), '[paced]': float(os.environ.get('AUTOBOTS_TEST_PACED', '1'))}
scripted.STEPS[1][1]['content'] = f"# Totals\n\nTotal: 42\n\n{os.environ['AUTOBOTS_TEST_CANARY']}\n"


async def handle(request: httpx.Request) -> httpx.Response:
    text = request.content.decode(errors='replace')
    with BODIES.open('a') as stream:
        stream.write(json.dumps({'at': time.time(), 'body': text,
                                 'headers': {name: value for name, value in request.headers.items() if name.lower() != 'authorization'}}) + '\n')
    for tag, seconds in DELAY.items():
        if tag in text:
            await asyncio.sleep(seconds)
    return scripted.handle(request)


def client_factory(key: str) -> Any:
    return default_sdk_client(key, async_http=httpx.AsyncClient(transport=httpx.MockTransport(handle)))


if __name__ == '__main__':
    asyncio.run(main(client_factory=client_factory, fetch_catalog=scripted.fetch_catalog))
