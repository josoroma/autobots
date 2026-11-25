"""The isolated browser's DevTools client and request guard: US-14.13, PRD-Tool-Catalog BX-02 and
Decision 0018.

The guard refuses what the egress proxy can't see inside TLS: any request that isn't a GET or HEAD,
or that carries a body, and any scheme but https, data, blob and about. Downloads are denied. It
also logs each page's committed top-frame navigations, those that landed on an error page, any
download that began, form submissions and bot checks, which browser-use's outcome is judged by
(Decision 0035 Y5, Y10, `browser_use_box`). A browser-use session's guard also lets submits through
(`SUBMIT_METHODS`). A request whose user agent isn't the browser's own is refused (Decision 0038
Z13). On a stealth browse on browser-use the guard is patient (Decision 0038 Z7 to Z9): it lets the
challenge hosts load as parts of a page, and gives a check that is the page time to clear by itself.
This module is in the images' fingerprint
(`browser_qualification.FINGERPRINTED`).
"""

import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import websockets
from websockets.asyncio.client import ClientConnection

READ_METHODS = frozenset({"GET", "HEAD"})
# Decision 0035 Y5: a browser-use session, which runs only under YOLO, may also submit, with a
# body, and send a POST's CORS preflight. Every other method stays refused.
SUBMIT_METHODS = frozenset({"GET", "HEAD", "POST", "OPTIONS"})
FORM_SUBMISSIONS = frozenset({"formSubmissionGet", "formSubmissionPost"})
_RECAPTCHA = re.compile(r"/recaptcha/(api2|enterprise)/(anchor|bframe)")
_GOOGLE = re.compile(r"^(www\.)?google\.[a-z.]+$")
# Decision 0038 Z7: what a stealth browse on browser-use may reach as parts of a page, with their
# subdomains, so a check that needs nobody can finish. Never as a page of its own.
TURNSTILE = "challenges.cloudflare.com"
CHALLENGE_HOSTS = (TURNSTILE, "captcha-delivery.com", "datadome.co")
# Z8: how long a check that is the page may take to clear, and how long a page that followed one
# must show none before the browse goes on.
CLEAR_SECONDS = 20.0
QUIET_SECONDS = 2.0
POLL_SECONDS = 0.25


def bot_check_host(url: str, resource_type: str | None = None) -> str | None:
    """The host of a bot check or CAPTCHA this URL shows, from the page itself (Decision 0035 Y10,
    Y16): reCAPTCHA's visible checkbox or its challenge, an hCaptcha, Cloudflare challenge,
    DataDome or Arkose frame, or Google's "sorry" page. An invisible reCAPTCHA or Cloudflare's
    silent detection script on an ordinary page isn't one. Only the host is kept."""
    parts = urlsplit(url)
    host, path = (parts.hostname or "").lower(), parts.path
    document = resource_type in (None, "Document")
    recaptcha = _RECAPTCHA.search(path)
    if recaptcha and (recaptcha.group(2) == "bframe" or "size=invisible" not in parts.query):
        return host
    challenge = "/cdn-cgi/challenge-platform/" in path and "/orchestrate/" in path
    framed = document and (
        host.endswith(("hcaptcha.com", "arkoselabs.com", "funcaptcha.com"))
        or host == "challenges.cloudflare.com"
    )
    sorry = bool(_GOOGLE.match(host)) and path.startswith("/sorry/")
    if challenge or framed or sorry or host.endswith("captcha-delivery.com"):
        return host
    return None


def under(host: str, domains: tuple[str, ...]) -> bool:
    """A host is under a domain when it is that domain or one of its subdomains."""
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def asks_a_person(url: str, resource_type: str | None = None) -> str | None:
    """The host of a check that a person must answer (Decision 0038 Z9): a visible reCAPTCHA or its
    challenge, an hCaptcha or an Arkose frame."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    recaptcha = _RECAPTCHA.search(parts.path)
    visible = recaptcha and (recaptcha.group(2) == "bframe" or "size=invisible" not in parts.query)
    framed = resource_type in (None, "Document") and host.endswith(
        ("hcaptcha.com", "arkoselabs.com", "funcaptcha.com")
    )
    return host if visible or framed else None


def is_the_page(url: str, resource_type: str | None = None) -> str | None:
    """The host of a check that is the page itself (Decision 0038 Z8): Google's "sorry" page, a
    Cloudflare challenge on the site's own host, or a DataDome frame. A Turnstile frame loads the
    same Cloudflare path from its own host, and isn't one (Z9)."""
    parts = urlsplit(url)
    host, path = (parts.hostname or "").lower(), parts.path
    sorry = bool(_GOOGLE.match(host)) and path.startswith("/sorry/")
    cloudflare = (
        host != TURNSTILE and "/cdn-cgi/challenge-platform/" in path and "/orchestrate/" in path
    )
    datadome = resource_type in (None, "Document") and under(host, ("captcha-delivery.com",))
    return host if sorry or cloudflare or datadome else None


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


@dataclass(frozen=True)
class Patience:
    """What a stealth browse on browser-use may reach as parts of a page, and how long a check that
    is the page may take to clear (Decision 0038 Z7, Z8)."""

    hosts: tuple[str, ...] = CHALLENGE_HOSTS
    seconds: float = CLEAR_SECONDS
    quiet: float = QUIET_SECONDS


@dataclass
class RequestGuard:
    """Refuses requests the proxy can't see inside TLS, on every page, frame and worker."""

    cdp: Cdp
    refused: list[dict[str, str]] = field(default_factory=list)
    # A browser-use session's guard, which lets submits through (SUBMIT_METHODS).
    submits: bool = False
    # Committed top-frame URLs, the URLs whose top-frame navigation landed on an error page, and
    # downloads that began, each for the pages this guard attached to.
    navigated: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    downloads: int = 0
    # The browser's own user agent, and the top-frame navigations that named another (Decision 0038
    # Z13). Each page session's target is its main frame, which tells such a navigation.
    user_agent: str | None = None
    disguised: int = 0
    frames: dict[str, str] = field(default_factory=dict)
    # Decision 0038 Z7 to Z9. The checks each page session is showing, when the first began, when a
    # page last followed one, and top-frame navigations to a challenge host.
    patience: Patience | None = None
    checking: dict[str, str] = field(default_factory=dict)
    since: float | None = None
    moved: float = 0.0
    barred: int = 0
    clock: Callable[[], float] = time.monotonic
    pages: set[str] = field(default_factory=set)
    # The page session that navigated last, form submissions as host and path, and the hosts of
    # bot checks seen (Decision 0035 Y10, Y11).
    latest: str | None = None
    submitted: list[str] = field(default_factory=list)
    bot_checks: list[str] = field(default_factory=list)

    async def start(self) -> None:
        version = await self.cdp.send("Browser.getVersion")
        self.user_agent = version.get("result", {}).get("userAgent")
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
                main = target["targetId"] if target["type"] == "page" else None
                await self._guard(attached["result"]["sessionId"], main=main)

    def refusals(self) -> int:
        """Top-frame navigations that landed on an error page, named another user agent or went to
        a challenge host, and downloads that began."""
        return len(self.failed) + self.downloads + self.disguised + self.barred

    async def settle(self) -> None:
        """Waits while a page shows a check that may clear by itself. One still showing when its
        time is up is a bot check (Decision 0038 Z8)."""
        if self.patience is None:
            return
        while self.since is not None:
            now = self.clock()
            if not self.checking and now - self.moved >= self.patience.quiet:
                self.since = None
            elif self.checking and now - self.since >= self.patience.seconds:
                self.bot_checks.extend(self.checking.values())
                self.checking.clear()
                self.since = None
            else:
                await asyncio.sleep(POLL_SECONDS)

    async def _guard(self, session: str, *, main: str | None = None) -> None:
        """Guards a session: a page's, whose main frame is `main`, or a frame's or worker's."""
        await self.cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]}, session)
        if main is not None:
            self.pages.add(session)
            self.frames[session] = main
            await self.cdp.send("Page.enable", {}, session)
        await self.cdp.send(
            "Target.setAutoAttach",
            {"autoAttach": True, "waitForDebuggerOnStart": True, "flatten": True},
            session,
        )
        await self.cdp.send("Runtime.runIfWaitingForDebugger", {}, session)

    def _navigated(self, session: str, frame: dict[str, Any]) -> None:
        if frame.get("parentId"):
            return
        self.latest = session
        if frame.get("unreachableUrl"):
            self.failed.append(str(frame["unreachableUrl"]))
            return
        url = str(frame.get("url", ""))
        self.navigated.append(url)
        # Another page took the place of the one that showed a check, unless this shows one too.
        if self.checking.pop(session, None) is not None:
            self.moved = self.clock()
        self._bot_check(session, url)

    def _bot_check(self, session: str, url: str, resource_type: str | None = None) -> None:
        if self.patience is None:
            host = bot_check_host(url, resource_type)
            if host is not None:
                self.bot_checks.append(host)
            return
        person = asks_a_person(url, resource_type)
        if person is not None:
            self.bot_checks.append(person)
            return
        page = is_the_page(url, resource_type)
        if page is not None:
            self.checking[session] = page
            self.since = self.clock() if self.since is None else self.since

    def _submitted(self, params: dict[str, Any]) -> None:
        if params.get("reason") in FORM_SUBMISSIONS:
            parts = urlsplit(str(params.get("url", "")))
            self.submitted.append(f"{(parts.hostname or '').lower()}{parts.path or '/'}")

    def _own_agent(self, request: dict[str, Any]) -> bool:
        """Whether a request says it comes from this browser. One with no user agent, as a data URL
        has none, says nothing else."""
        headers = request.get("headers") or {}
        named = next((v for k, v in headers.items() if k.lower() == "user-agent"), None)
        return named is None or self.user_agent is None or named == self.user_agent

    def _top(self, session: str, params: dict[str, Any]) -> bool:
        """Whether a paused request is a page's own top-frame navigation."""
        return (
            params.get("resourceType") == "Document"
            and session in self.frames
            and params.get("frameId") == self.frames[session]
        )

    def _challenge(self, url: str) -> bool:
        host = (urlsplit(url).hostname or "").lower()
        return self.patience is not None and under(host, self.patience.hosts)

    def _allowed(self, request: dict[str, Any], scheme: str) -> bool:
        if scheme not in ALLOWED_SCHEMES:
            return False
        if self.submits:
            return request["method"] in SUBMIT_METHODS and (
                scheme == "https" or request["method"] in READ_METHODS
            )
        return request["method"] in READ_METHODS and not request.get("hasPostData")

    async def _event(self, message: dict[str, Any]) -> None:
        method, params = message["method"], message.get("params", {})
        session = message.get("sessionId")
        try:
            if method == "Target.attachedToTarget":
                target = params.get("targetInfo", {})
                main = str(target.get("targetId", "")) if target.get("type") == "page" else None
                await self._guard(params["sessionId"], main=main)
            elif method == "Page.frameNavigated" and session in self.pages:
                self._navigated(session, params["frame"])
            elif method == "Page.frameRequestedNavigation" and session in self.pages:
                self._submitted(params)
            elif method == "Browser.downloadWillBegin":
                # Code driving the browser over CDP can turn downloads back on, past Chromium's
                # policy (Decision 0035 Y6), so one that begins anyway is cancelled and counted.
                self.downloads += 1
                await self.cdp.send("Browser.cancelDownload", {"guid": params["guid"]})
            elif method == "Fetch.requestPaused" and session is not None:
                request = params["request"]
                scheme = request["url"].split(":", 1)[0].lower()
                self._bot_check(session, request["url"], params.get("resourceType"))
                own, top = self._own_agent(request), self._top(session, params)
                if not own and top:
                    self.disguised += 1
                barred = top and self._challenge(request["url"])
                if barred:
                    self.barred += 1
                if own and not barred and self._allowed(request, scheme):
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
