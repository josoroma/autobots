"""What the API process holds, declared once (refactor plan R-54, PAPI-08).

The entry point or a test builds an `AppResources`, and `create_app` stores it, opening nothing.
The lifespan opens the pool and sets it here, then closes it. Handlers read these through
`app_resources`, never through `app.state` attributes of their own.
"""

from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request

from autobots.adapters.models.local_health import DIGESTS, Digests
from autobots.adapters.tool_registry import catalog
from autobots.api.errors import ApiError
from autobots.api.membership import DenyAllMembership, MembershipStore
from autobots.api.pool import Pool
from autobots.api.settings import Settings
from autobots.application.artifacts import PingableObjectStore
from autobots.application.operations import ProbeTimes
from autobots.application.provider_settings import ProviderContext
from autobots.application.tool_catalog import Catalog

# A stream ends after a while, and the client reconnects from its cursor.
DEFAULT_STREAM_SECONDS = 60.0
# Each live stream listens on a direct connection outside the pool. Past this many at once, a
# stream polls stored events only, as one does when LISTEN can't connect (PAPI-11).
MAX_LISTENERS = 10


class ListenerSlots:
    """How many streams hold a LISTEN connection now, in this process. One event loop serves every
    stream, and nothing awaits between reading the count and changing it."""

    def __init__(self, limit: int = MAX_LISTENERS) -> None:
        self.limit = limit
        self.held = 0

    def take(self) -> bool:
        if self.held >= self.limit:
            return False
        self.held += 1
        return True

    def give_back(self) -> None:
        self.held -= 1


@dataclass
class AppResources:
    """`tools` is the tool catalog the routes read and admit through: by default the one over the
    registry the worker builds (adapters/tool_registry.py, XMOD-01). `provider_context` is the live
    mapping, so a key is resolved again for each attempt (model-gateway rule). Without one, as some
    tests build an app, provider settings are unavailable. `pool` is the lifespan's."""

    settings: Settings = field(default_factory=Settings)
    membership: MembershipStore = field(default_factory=DenyAllMembership)
    tools: Catalog = field(default_factory=catalog)
    provider_context: ProviderContext | None = None
    object_store: PingableObjectStore | None = None
    stream_seconds: float = DEFAULT_STREAM_SECONDS
    probe_times: ProbeTimes = field(default_factory=ProbeTimes)
    listener_slots: ListenerSlots = field(default_factory=ListenerSlots)
    pool: Pool | None = None
    # The owner's llama-server, as Settings and Home check it (Decision 0041 A13). None reads the
    # port from the environment, and a transport is for tests only.
    local_port: int | None = None
    local_transport: Any = None
    local_digests: Digests = field(default_factory=lambda: DIGESTS)


def resources_of(app: FastAPI) -> AppResources:
    """The one read of `app.state`, which starlette leaves untyped."""
    resources: AppResources = app.state.resources
    return resources


def app_resources(request: Request) -> AppResources:
    return resources_of(request.app)


def request_pool(request: Request) -> Pool:
    """The open pool, or 503 when the service has no database."""
    pool = app_resources(request).pool
    if pool is None:
        raise ApiError(503, "service_unavailable", "The database is unavailable.")
    return pool
