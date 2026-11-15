"""Whether OpenRouter's public catalog answers, for every surface that shows it (POPS-13).

Only the public catalog is read: no model call is made, and the answer is independent of any key
(MP-04, SP-007). Each surface keeps its own time limit: Operations waits `OPERATIONS_SECONDS`, as a
page load must not wait long, and Settings and the model list wait `SETTINGS_SECONDS`, the HTTP
client's own limit (adapters/models/openrouter_metadata.py TIMEOUT_SECONDS).
"""

import asyncio
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

OPERATIONS_SECONDS = 3.0
SETTINGS_SECONDS = 15.0

CatalogStatus = Literal["available", "unavailable", "unknown"]
Fetch = Callable[[], Awaitable[dict[str, Any] | None]]


@dataclass(frozen=True)
class CatalogCheck:
    """The catalog's state, its payload when it answered, and how long that took."""

    status: CatalogStatus
    payload: dict[str, Any] | None = None
    milliseconds: int | None = None


async def check_catalog(fetch: Fetch | None, seconds: float) -> CatalogCheck:
    """Unknown with no fetcher. Every expected failure reads as unavailable: no answer within
    `seconds`, a lost connection, a reply that isn't JSON, or no payload."""
    if fetch is None:
        return CatalogCheck("unknown")
    started = time.monotonic()
    try:
        payload = await asyncio.wait_for(fetch(), seconds)
    except (TimeoutError, OSError, ValueError):
        return CatalogCheck("unavailable")
    if payload is None:
        return CatalogCheck("unavailable")
    return CatalogCheck("available", payload, math.ceil((time.monotonic() - started) * 1000))
