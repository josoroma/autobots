"""One installation readiness gate for a person's run and a due routine (LM-07, Decision 0023 E2).

The API's `require_ready` and the worker's maintenance step both refuse on `first_blocking` of
`installation_conditions`, so a new blocking condition reaches both (refactor plan R-24, POPS-02).
Its settings are read from the environment once per process by the entry point (PAPI-10).
"""

from collections.abc import AsyncIterator, Iterable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from autobots.application.operations import (
    Condition,
    ProbeTimes,
    StoragePing,
    database_conditions,
    disk_condition,
    stops_admission,
    storage_condition,
)
from autobots.application.sql import SqlConnection, SqlPool

DATA_ROOT = "AUTOBOTS_CONFIG_ROOT"
MIN_FREE_BYTES = "AUTOBOTS_MIN_FREE_BYTES"
DEFAULT_MIN_FREE_BYTES = 2 * 1024**3
MALFORMED_MINIMUM = (
    f"{MIN_FREE_BYTES} must be a whole number of bytes, 0 or more. Leave it unset for 2 GiB."
)


class MalformedSetting(ValueError):
    """A readiness setting the process can't start with. The message names it, never its value."""


@dataclass(frozen=True)
class ReadinessSettings:
    """The host disk under the app's data, and the free space admission needs on it."""

    data_root: Path = Path(".")
    min_free_bytes: int = DEFAULT_MIN_FREE_BYTES

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> Self:
        """Unset or blank means the default, as it does for the data root."""
        data_root = Path(environ.get(DATA_ROOT) or ".")
        raw = environ.get(MIN_FREE_BYTES, "").strip()
        if not raw:
            return cls(data_root, DEFAULT_MIN_FREE_BYTES)
        try:
            minimum = int(raw)
        except ValueError:
            raise MalformedSetting(MALFORMED_MINIMUM) from None
        if minimum < 0:
            raise MalformedSetting(MALFORMED_MINIMUM)
        return cls(data_root, minimum)


# The API's pool, or `LentConnection` around the worker's own connection.
ConnectionSource = SqlPool


class LentConnection:
    """A connection its holder lends as a pool lends one, so the worker's own connection answers
    the probe the API makes through its pool."""

    def __init__(self, connection: SqlConnection) -> None:
        self._connection = connection

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[SqlConnection]:
        yield self._connection


async def installation_conditions(
    database: ConnectionSource | None,
    store: StoragePing | None,
    settings: ReadinessSettings,
    probes: ProbeTimes | None = None,
) -> list[Condition]:
    """Database, schema, hold, adapter, Storage and disk, the order a refusal is read in. When the
    database answers, its answer time joins `probes`."""
    database_state, schema, hold, adapter = await database_conditions(database, probes)
    storage = await storage_condition(store)
    disk = disk_condition(settings.data_root, settings.min_free_bytes)
    return [database_state, schema, hold, adapter, storage, disk]


def first_blocking(conditions: Iterable[Condition]) -> Condition | None:
    """The refusal: the first condition that stops admission, or None when none does."""
    return next((item for item in conditions if stops_admission(item)), None)
