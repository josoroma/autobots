"""The owner's llama-server's health for one local profile, as Settings and Home show it (Decision
0041 A3, A13; US-23.3).

`/v1/models` must report exactly the profile's model ID, as before every call. `/props` names the
file the server loaded, and that file's SHA-256 is compared with the profile's pin. Hashing several
gigabytes takes seconds, so it runs once per path, size and modification time, off the event loop,
and the health reads "checking" until it's done. Home asks without the hash, so it never waits.
Nothing here starts the server, reads a key or reaches beyond 127.0.0.1.
"""

import asyncio
import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from autobots.adapters.models.local_server import IDENTITY_SECONDS, base_url
from autobots.domain.models import ModelProfile

Status = Literal["ready", "other_model", "not_running"]
CHUNK_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Health:
    status: Status
    served_model_id: str | None = None
    sha256_matches: bool | None = None
    sha256_checking: bool = False


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class Digests:
    """Each served file's SHA-256, hashed once per path, size and modification time. One per
    process. `hash_file` is for tests."""

    hash_file: Callable[[str], str] = file_sha256
    _known: dict[tuple[str, int, int], str] = field(default_factory=dict)
    _running: dict[tuple[str, int, int], asyncio.Task[None]] = field(default_factory=dict)

    def lookup(self, path: str) -> str | None:
        """The file's digest if it's known, starting the hash if it isn't. None while it runs, and
        for a path that isn't a regular file."""
        try:
            facts = os.stat(path)
        except OSError:
            return None
        key = (path, facts.st_size, facts.st_mtime_ns)
        if key in self._known:
            return self._known[key]
        if key not in self._running:
            self._running[key] = asyncio.ensure_future(self._hash(key))
        return None

    def checking(self, path: str) -> bool:
        return any(key[0] == path and not task.done() for key, task in self._running.items())

    async def settled(self) -> None:
        """Waits for every hash under way, for tests."""
        await asyncio.gather(*self._running.values(), return_exceptions=True)

    async def _hash(self, key: tuple[str, int, int]) -> None:
        try:
            self._known[key] = await asyncio.to_thread(self.hash_file, key[0])
        except OSError:
            pass
        finally:
            self._running.pop(key, None)


DIGESTS = Digests()


async def runtime_health(
    profile: ModelProfile,
    port: int,
    *,
    with_digest: bool,
    transport: httpx.AsyncBaseTransport | None = None,
    digests: Digests = DIGESTS,
) -> Health:
    try:
        async with httpx.AsyncClient(transport=transport, timeout=IDENTITY_SECONDS) as http:
            listed = await http.get(base_url(port) + "/models")
            served = [str(item.get("id")) for item in listed.json().get("data", [])]
            props = await http.get(f"http://127.0.0.1:{port}/props") if with_digest else None
    except (httpx.TransportError, ValueError, AttributeError, TypeError):
        return Health("not_running")
    if served != [profile.wire_id]:
        return Health("other_model", served[0] if served else None)
    if props is None or profile.local is None:
        return Health("ready", profile.wire_id)
    try:
        path = props.json().get("model_path")
    except (ValueError, AttributeError):
        path = None
    if not isinstance(path, str) or not path:
        return Health("ready", profile.wire_id)
    digest = digests.lookup(path)
    if digest is None:
        return Health("ready", profile.wire_id, None, digests.checking(path))
    return Health("ready", profile.wire_id, digest == profile.local.sha256)
