"""Supabase Storage through its API. The service key bypasses Storage's own rules.

So this refuses any path outside a workspace and run namespace, and callers check the workspace from
the database row, never from a path a request supplied.
"""

import re
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import SecretStr

BUCKET = "workspace-artifacts"
_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_SCOPED = re.compile(rf"^{_UUID}/{_UUID}(/[A-Za-z0-9._-]+)?$")


class StorageUnavailable(Exception):
    """Storage couldn't answer, so nothing can be said about the object."""


def _scoped(path: str) -> str:
    if not _SCOPED.fullmatch(path):
        raise ValueError("object paths stay inside a workspace and run namespace")
    return quote(path)


class SupabaseObjectStore:
    def __init__(
        self, base_url: str, service_key: SecretStr, *, transport: Any = None, timeout: float = 30
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/storage/v1"
        self._key = service_key
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        secret = self._key.get_secret_value()
        return httpx.AsyncClient(
            base_url=self._url,
            headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
            timeout=self._timeout,
            follow_redirects=False,
            transport=self._transport,
        )

    async def ping(self) -> None:
        """Storage itself answering, past the gateway, or StorageUnavailable."""
        async with self._client() as client:
            reply = await client.get(f"/bucket/{BUCKET}")
        if reply.status_code != 200:
            raise StorageUnavailable(f"the bucket check answered {reply.status_code}")

    async def put(self, path: str, content: bytes, media_type: str) -> bool:
        """False when the object already exists. It is never overwritten."""
        async with self._client() as client:
            reply = await client.post(
                f"/object/{BUCKET}/{_scoped(path)}",
                content=content,
                headers={"Content-Type": media_type, "x-upsert": "false"},
            )
        if reply.status_code == 200:
            return True
        if reply.status_code in {400, 409} and "exists" in reply.text.lower():
            return False
        raise StorageUnavailable(f"upload answered {reply.status_code}")

    async def get(self, path: str) -> bytes | None:
        async with self._client() as client:
            reply = await client.get(f"/object/{BUCKET}/{_scoped(path)}")
        if reply.status_code == 200:
            return reply.content
        if reply.status_code in {400, 404}:
            return None
        raise StorageUnavailable(f"download answered {reply.status_code}")

    async def remove(self, path: str) -> None:
        async with self._client() as client:
            reply = await client.delete(f"/object/{BUCKET}/{_scoped(path)}")
        if reply.status_code not in {200, 400, 404}:
            raise StorageUnavailable(f"removal answered {reply.status_code}")

    async def names(self, prefix: str) -> list[str]:
        """Full paths of the objects directly under a run's namespace."""
        _scoped(prefix)
        async with self._client() as client:
            reply = await client.post(
                f"/object/list/{BUCKET}", json={"prefix": prefix, "limit": 1000}
            )
        if reply.status_code != 200:
            raise StorageUnavailable(f"listing answered {reply.status_code}")
        return [f"{prefix}/{item['name']}" for item in reply.json()]
