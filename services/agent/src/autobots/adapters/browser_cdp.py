"""The isolated browser's DevTools client and request guard: US-14.13, PRD-Tool-Catalog BX-02 and
Decision 0018.

The guard refuses what the egress proxy can't see inside TLS: any request that isn't a GET or HEAD,
or that carries a body, and any scheme but https, data, blob and about. Downloads are denied. This
module is in the images' fingerprint (`browser_qualification.FINGERPRINTED`).
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

READ_METHODS = frozenset({"GET", "HEAD"})
# Everything else, file and plain http included, is refused before it loads.
ALLOWED_SCHEMES = frozenset({"https", "data", "blob", "about"})


class Cdp:
    """A small DevTools client: commands by id, events by method and session."""

    def __init__(self, socket: ClientConnection) -> None:
        self._socket = socket
        self._next = 0
        self._waiting: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self.handlers: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._tasks: set[asyncio.Future[None]] = set()
        self._reader = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, url: str) -> "Cdp":
        socket = await websockets.connect(url, max_size=64 * 1024 * 1024, proxy=None)
        return cls(socket)

    async def _read(self) -> None:
        try:
            async for raw in self._socket:
                message = json.loads(raw)
                if "id" in message and message["id"] in self._waiting:
                    self._waiting.pop(message["id"]).set_result(message)
                elif "method" in message:
                    for handler in list(self.handlers):
                        task = asyncio.ensure_future(handler(message))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
        except websockets.ConnectionClosed:
            pass
        finally:
            for future in self._waiting.values():
                if not future.done():
                    future.set_exception(ConnectionError("cdp_closed"))

    async def send(
        self, method: str, params: dict[str, Any] | None = None, session: str | None = None
    ) -> dict[str, Any]:
        self._next += 1
        message: dict[str, Any] = {"id": self._next, "method": method, "params": params or {}}
        if session is not None:
            message["sessionId"] = session
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._waiting[self._next] = future
        await self._socket.send(json.dumps(message))
        return await asyncio.wait_for(future, 30)

    async def close(self) -> None:
        await self._socket.close()
        self._reader.cancel()


@dataclass
class RequestGuard:
    """Refuses requests the proxy can't see inside TLS, on every page, frame and worker."""

    cdp: Cdp
    refused: list[dict[str, str]] = field(default_factory=list)

    async def start(self) -> None:
        self.cdp.handlers.append(self._event)
        await self.cdp.send(
            "Browser.setDownloadBehavior", {"behavior": "deny", "eventsEnabled": True}
        )
        await self.cdp.send(
            "Target.setAutoAttach",
            {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True},
        )
        targets = (await self.cdp.send("Target.getTargets"))["result"]["targetInfos"]
        for target in targets:
            if target["type"] in ("page", "iframe"):
                attached = await self.cdp.send(
                    "Target.attachToTarget", {"targetId": target["targetId"], "flatten": True}
                )
                await self._guard(attached["result"]["sessionId"])

    async def _guard(self, session: str) -> None:
        await self.cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}, session)
        await self.cdp.send(
            "Target.setAutoAttach",
            {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True},
            session,
        )
        await self.cdp.send("Runtime.runIfWaitingForDebugger", {}, session)

    async def _event(self, message: dict[str, Any]) -> None:
        method, params = message["method"], message.get("params", {})
        session = message.get("sessionId")
        try:
            if method == "Target.attachedToTarget":
                await self._guard(params["sessionId"])
            elif method == "Fetch.requestPaused" and session is not None:
                request = params["request"]
                scheme = request["url"].split(":", 1)[0].lower()
                if (
                    scheme in ALLOWED_SCHEMES
                    and request["method"] in READ_METHODS
                    and not request.get("hasPostData")
                ):
                    await self.cdp.send(
                        "Fetch.continueRequest", {"requestId": params["requestId"]}, session
                    )
                else:
                    host = request["url"].split("://", 1)[-1].split("/", 1)[0]
                    self.refused.append(
                        {"method": request["method"], "scheme": scheme, "host": host}
                    )
                    await self.cdp.send(
                        "Fetch.failRequest",
                        {"requestId": params["requestId"], "errorReason": "BlockedByClient"},
                        session,
                    )
        except (ConnectionError, TimeoutError, KeyError):
            return
