"""The isolated browser executor, US-14.13, PRD-Tool-Catalog BX-01 to BX-05 and Decision 0018.

One browsing call gets one session: a hardened Chromium container on an internal Docker network,
and an egress sidecar that is its only way out and the only door to its DevTools, published on this
Mac's loopback behind a per-session token. Nothing of the worker's environment is passed in. The
session belongs to one attempt: losing the lease, cancelling the run or reaching the time cap
removes it, and a sweeper removes any a crashed worker left, by their labels.

A request guard attached over CDP refuses what the proxy can't see inside TLS: any request that
isn't a GET or HEAD, or that carries a body, and any scheme but https, data, blob and about.
Downloads are denied over CDP. The Docker CLI is driven directly, so no Docker SDK is installed.
"""

import asyncio
import hashlib
import json
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import websockets

LABEL = "autobots.browser"
BROWSER_IMAGE = "autobots-browser:local"
PROXY_IMAGE = "autobots-egress:local"
READ_METHODS = frozenset({"GET", "HEAD"})
# Everything else, file and plain http included, is refused before it loads.
ALLOWED_SCHEMES = frozenset({"https", "data", "blob", "about"})
# Only what Docker itself needs. A container gets nothing from here except what `-e` names.
DOCKER_ENV_NAMES = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")


class ExecutorUnavailable(Exception):
    """Docker or an image is missing, or a container wouldn't start. A typed reason, no output."""


@dataclass(frozen=True)
class ExecutorConfig:
    """Decision 0018 B2. Tests narrow the caps; nothing widens them."""

    browser_image: str = BROWSER_IMAGE
    proxy_image: str = PROXY_IMAGE
    cpus: str = "1"
    memory: str = "1g"
    pids: int = 256
    tmpfs: str = "256m"
    seconds: float = 300.0
    max_requests: int = 500
    max_bytes: int = 50 * 1024 * 1024
    docker: str = "docker"
    environ: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BrowserSession:
    name: str
    token: str
    port: int
    run_id: str
    generation: int

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.port}/{self.token}"

    async def websocket_url(self) -> str:
        """The browser's DevTools socket, through the gate."""
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            reply = await client.get(f"{self.base}/json/version")
        reply.raise_for_status()
        inner = str(reply.json()["webSocketDebuggerUrl"])
        path = inner.split("/devtools/", 1)[1]
        return f"ws://127.0.0.1:{self.port}/{self.token}/devtools/{path}"


class BrowserExecutor:
    def __init__(
        self, config: ExecutorConfig | None = None, environ: dict[str, str] | None = None
    ) -> None:
        self.config = config or ExecutorConfig()
        source = environ if environ is not None else dict(os.environ)
        self._env = {name: source[name] for name in DOCKER_ENV_NAMES if name in source}

    async def _run(self, *arguments: str, seconds: float = 60.0) -> tuple[int, bytes, bytes]:
        """One Docker CLI call, bounded, since a saturated container can stall an exec."""
        process = await asyncio.create_subprocess_exec(
            self.config.docker,
            *arguments,
            env=self._env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(process.communicate(), seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            return -1, b"", b"timed out"
        return process.returncode or 0, out, err

    async def _docker(self, *arguments: str, check: bool = True) -> str:
        code, out, _ = await self._run(*arguments)
        if check and code != 0:
            raise ExecutorUnavailable(f"docker_{arguments[0]}_failed")
        return out.decode()

    async def start(
        self, run_id: UUID | str, generation: int, allowed_hosts: tuple[str, ...]
    ) -> BrowserSession:
        """`allowed_hosts` are the only hosts the browser may reach, with their subdomains."""
        for host in allowed_hosts:
            if not host or any(mark in host for mark in "/, \t") or host.startswith("."):
                raise ExecutorUnavailable("allowed_host_malformed")
        name = f"autobots-browser-{secrets.token_hex(6)}"
        token = secrets.token_urlsafe(24)
        labels = [
            "--label", f"{LABEL}=1",
            "--label", f"{LABEL}.run={run_id}",
            "--label", f"{LABEL}.generation={generation}",
            "--label", f"{LABEL}.session={name}",
        ]  # fmt: skip
        hardening = [
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.config.pids),
        ]  # fmt: skip
        try:
            await self._docker("network", "create", "--internal", *labels, f"{name}-net")
            # The proxy's own way out, a network of its own so Docker's DNS finds the browser.
            await self._docker("network", "create", *labels, f"{name}-out")
            await self._docker(
                "run", "-d", "--name", f"{name}-proxy", *labels, *hardening,
                "--network", f"{name}-out",
                "--publish", "127.0.0.1::9223",
                "--memory", "256m", "--cpus", "0.5",
                "-e", f"AUTOBOTS_CDP_TOKEN={token}",
                "-e", f"AUTOBOTS_BROWSER_HOST={name}-browser",
                "-e", f"AUTOBOTS_MAX_REQUESTS={self.config.max_requests}",
                "-e", f"AUTOBOTS_MAX_BYTES={self.config.max_bytes}",
                "-e", f"AUTOBOTS_ALLOWED_HOSTS={','.join(allowed_hosts)}",
                self.config.proxy_image,
            )  # fmt: skip
            await self._docker(
                "network", "connect", "--alias", "proxy", f"{name}-net", f"{name}-proxy"
            )
            await self._docker(
                "run", "-d", "--name", f"{name}-browser", *labels, *hardening,
                "--network", f"{name}-net",
                "--tmpfs", f"/tmp:rw,size={self.config.tmpfs},mode=1777",
                "--memory", self.config.memory, "--memory-swap", self.config.memory,
                "--cpus", self.config.cpus,
                "-e", "HOME=/tmp",
                self.config.browser_image,
            )  # fmt: skip
            mapping = (await self._docker("port", f"{name}-proxy", "9223")).split()[0]
            port = int(mapping.rsplit(":", 1)[1])
        except (ExecutorUnavailable, IndexError, ValueError):
            await self.remove(name)
            raise ExecutorUnavailable("executor_start_failed") from None
        session = BrowserSession(name, token, port, str(run_id), generation)
        await self._ready(session)
        return session

    async def _ready(self, session: BrowserSession, seconds: float = 20.0) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                await session.websocket_url()
                return
            except (httpx.HTTPError, KeyError, IndexError, ValueError):
                await asyncio.sleep(0.25)
        await self.remove(session.name)
        raise ExecutorUnavailable("executor_not_ready")

    async def remove(self, name: str) -> None:
        await self._docker("rm", "-f", f"{name}-browser", f"{name}-proxy", check=False)
        await self._docker("network", "rm", f"{name}-net", f"{name}-out", check=False)

    async def stop(self, session: BrowserSession) -> None:
        await self.remove(session.name)

    async def exists(self, session: BrowserSession) -> bool:
        out = await self._docker(
            "ps", "-a", "--filter", f"label={LABEL}.session={session.name}",
            "--format", "{{.Names}}", check=False,
        )  # fmt: skip
        return bool(out.strip())

    async def running(self, session: BrowserSession) -> tuple[bool, bool]:
        """Whether the browser runs, and whether Docker killed it for memory."""
        out = await self._docker(
            "inspect", "--format", "{{.State.Running}} {{.State.OOMKilled}}",
            f"{session.name}-browser", check=False,
        )  # fmt: skip
        parts = out.split()
        return (parts[:1] == ["true"], parts[1:2] == ["true"])

    async def inspect(self, session: BrowserSession) -> dict[str, Any]:
        out = await self._docker("inspect", f"{session.name}-browser", f"{session.name}-proxy")
        browser, proxy = json.loads(out)
        return {"browser": browser, "proxy": proxy}

    async def proxy_log(self, session: BrowserSession) -> list[dict[str, Any]]:
        out = await self._docker("logs", f"{session.name}-proxy", check=False)
        entries = []
        for line in out.splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
        return entries

    async def sweep(self, alive: Callable[[str, int], Awaitable[bool]]) -> list[str]:
        """Removes every labelled session whose attempt no longer holds its run."""
        out = await self._docker(
            "ps", "-a", "--filter", f"label={LABEL}=1", "--format",
            '{{.Label "autobots.browser.session"}} {{.Label "autobots.browser.run"}} '
            '{{.Label "autobots.browser.generation"}}',
            check=False,
        )  # fmt: skip
        removed = []
        for line in sorted(set(out.splitlines())):
            parts = line.split()
            if len(parts) != 3 or not parts[2].isdigit():
                continue
            name, run_id, generation = parts[0], parts[1], int(parts[2])
            if not await alive(run_id, generation):
                await self.remove(name)
                removed.append(name)
        return removed

    async def cap_events(self, session: BrowserSession) -> tuple[int, int]:
        """How often the kernel enforced the memory and process caps: OOM kills, and forks refused
        at the process limit. Read from the container's own cgroup counters, one file at a time
        since both name a counter `max`. At the process limit even `docker exec` can't fork
        inside, so a refused or stalled exec, or a count held at the limit seen from outside,
        also says the cap is being enforced."""
        saturated = False

        async def counters(path: str) -> dict[str, int]:
            nonlocal saturated
            code, out, err = await self._run(
                "exec", f"{session.name}-browser", "cat", path, seconds=5.0
            )
            # Docker reports a refused exec on either stream, depending on where runc failed.
            if code != 0 and (b"Resource temporarily unavailable" in out + err or code == -1):
                saturated = True
            return {
                parts[0]: int(parts[1])
                for parts in (line.split() for line in out.decode().splitlines())
                if len(parts) == 2 and parts[1].isdigit()
            }

        memory = await counters("/sys/fs/cgroup/memory.events")
        pids = await counters("/sys/fs/cgroup/pids.events")
        code, out, _ = await self._run(
            "stats", "--no-stream", "--format", "{{.PIDs}}", f"{session.name}-browser", seconds=10.0
        )
        count = out.decode().strip()
        # Docker's count leaves out one task the cgroup holds, so the limit shows as one less.
        if code == 0 and count.isdigit() and int(count) >= self.config.pids - 1:
            saturated = True
        refused = pids.get("max", 0) or (1 if saturated else 0)
        return memory.get("oom_kill", 0), refused

    async def watch(
        self,
        session: BrowserSession,
        alive: Callable[[], Awaitable[bool]],
        seconds: float | None = None,
        every: float = 1.0,
    ) -> str:
        """Holds the session until its attempt ends. Returns why it was removed."""
        limit = self.config.seconds if seconds is None else seconds
        started = time.monotonic()
        reason = "removed"
        try:
            while True:
                running, killed = await self.running(session)
                if killed:
                    reason = "memory_cap"
                    break
                if not running:
                    reason = "browser_exited"
                    break
                oom_kills, refused_forks = await self.cap_events(session)
                if oom_kills:
                    reason = "memory_cap"
                    break
                if refused_forks:
                    reason = "process_cap"
                    break
                if time.monotonic() - started >= limit:
                    reason = "time_cap"
                    break
                if not await alive():
                    reason = "attempt_ended"
                    break
                await asyncio.sleep(every)
        finally:
            await self.stop(session)
        return reason


class Cdp:
    """A small DevTools client: commands by id, events by method and session."""

    def __init__(self, socket: Any) -> None:
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


def images_fingerprint(root: Path) -> dict[str, str]:
    """What a qualification is bound to: the image definitions and the proxy's code."""
    paths = [
        root / "infra/browser/browser.Dockerfile",
        root / "infra/browser/proxy.Dockerfile",
        root / "infra/browser/browser-entrypoint.js",
        root / "services/agent/src/autobots/adapters/egress_proxy.py",
        root / "services/agent/src/autobots/adapters/browser_executor.py",
    ]
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }


async def attempt_alive(connection: Any, scope: Any) -> bool:
    """The attempt still owns a running run, by database time, as the gateway decides it."""
    from autobots.application.tool_gateway import ownership_refusal

    return await ownership_refusal(connection, scope) is None


def lease_alive(connection: Any) -> Callable[[str, int], Awaitable[bool]]:
    """For the sweeper: a session lives only while its run's job is claimed at its generation."""

    async def alive(run_id: str, generation: int) -> bool:
        cursor = await connection.execute(
            "select 1 from app_private.run_jobs j join public.runs r on r.id = j.run_id "
            "where j.run_id::text = %s and j.generation = %s and j.status = 'claimed' "
            "and j.lease_expires_at > clock_timestamp() and r.status = 'running'",
            (run_id, generation),
        )
        return await cursor.fetchone() is not None

    return alive


QUALIFICATION = Path(".checks/browser-executor/qualification.json")
# Every case the live check must observe before the executor is reported qualified (BX-05).
REQUIRED_CASES = (
    "an allowed page loads through the proxy, connected to the address it checked",
    "only the hosts a call names are reached",
    "loopback, the Docker host and the stack's ports are refused",
    "private, metadata and loopback-resolving names are refused",
    "a script-driven redirect to a private address is refused",
    "subresources and a WebSocket to private addresses are refused",
    "a file URL is refused",
    "a download is refused",
    "a request with a body is refused",
    "the request and byte caps are enforced",
    "the proxy logs hosts, never paths or queries",
    "nothing of the host enters the container",
    "the CDP gate needs the session token",
    "the memory cap ends the session",
    "the process cap ends the session",
    "the time cap ends the session",
    "a cancelled run ends the session",
    "a lost lease ends the session",
    "the sweeper removes what a crashed worker left",
    "no host outside the qualification hosts was reached",
)


def executor_qualified(root: Path, report: Path = QUALIFICATION) -> bool:
    """Only after a passing live check, bound to today's image definitions and proxy code."""
    try:
        data = json.loads((root / report).read_text())
    except (OSError, ValueError):
        return False
    passed = {case.get("id") for case in data.get("cases", []) if case.get("status") == "passed"}
    return (
        data.get("status") == "passed"
        and all(case in passed for case in REQUIRED_CASES)
        and data.get("executor_fingerprint") == images_fingerprint(root)
    )
