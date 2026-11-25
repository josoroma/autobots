"""The isolated browser executor's Docker sessions, US-14.13, PRD-Tool-Catalog BX-01 to BX-05 and
Decision 0018.

One browsing call gets one session: a hardened Chromium container on an internal Docker network,
and an egress sidecar that is its only way out and the only door to its DevTools, published on this
Mac's loopback behind a per-session token. Nothing of the worker's environment is passed in. The
session belongs to one attempt: losing the lease, cancelling the run or reaching the time cap
removes it, and a sweeper removes any a crashed worker left, by their labels.

For a browse on browser-use (Decision 0035 Y5 and Y8), a third container joins the session's
internal network only and drives the session's Chromium over CDP, with the sidecar's model relay as
its only model. It gets the browser's hardening and caps, and nothing of the worker's environment.

A session's browser is the box's headless Chromium, or the stealth browser (Decision 0038 Z2 to Z4):
headed Google Chrome in its own image, with the workspace's time zone, in the same network, proxy,
guard and hardening. Only its process cap is higher.

The DevTools client and request guard are in `browser_cdp`, what a qualification binds is in
`browser_qualification`, and the checks that end a session are in `application/browser_leases`.
This module, those three and the images' sources are all in the images' fingerprint. The Docker CLI
is driven directly, so no Docker SDK is installed.
"""

import asyncio
import json
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx

from autobots.adapters.browser_cdp import CHALLENGE_HOSTS, Cdp, RequestGuard
from autobots.adapters.browser_qualification import (
    BROWSER,
    BROWSER_USE,
    DOCKER_ENV_NAMES,
    PROXY,
    STEALTH,
    executor_qualified,
)
from autobots.application.browser_leases import attempt_alive, lease_alive

# CHALLENGE_HOSTS, Cdp, RequestGuard and executor_qualified are named here too, because
# browsing_tool and browser_page import them from this module; attempt_alive and lease_alive,
# because tests/db/checks/browser_executor_check.py does.
__all__ = [
    "CHALLENGE_HOSTS",
    "LABEL",
    "BrowserExecutor",
    "BrowserSession",
    "Cdp",
    "ExecutorConfig",
    "ExecutorUnavailable",
    "ModelLink",
    "RequestGuard",
    "Stealth",
    "attempt_alive",
    "executor_qualified",
    "lease_alive",
]

LABEL = "autobots.browser"
# The session's DevTools forwarder and the sidecar's relay, as the browser-use container sees them.
DEVTOOLS_PORT = 9222
RELAY_URL = "http://proxy:9300/v1"


class ExecutorUnavailable(Exception):
    """Docker or an image is missing, or a container wouldn't start. A typed reason, no output."""


@dataclass(frozen=True)
class ExecutorConfig:
    """Decision 0018 B2. Tests narrow the caps; nothing widens them."""

    # The images whose fingerprint label `executor_qualified` checks (refactor plan R-57).
    browser_image: str = BROWSER.tag
    proxy_image: str = PROXY.tag
    browser_use_image: str = BROWSER_USE.tag
    stealth_image: str = STEALTH.tag
    cpus: str = "1"
    memory: str = "1g"
    pids: int = 256
    # Decision 0038 Z4: headed Chrome reaches 256 on an ordinary page of cross-site frames.
    stealth_pids: int = 512
    tmpfs: str = "256m"
    seconds: float = 300.0
    max_requests: int = 500
    max_bytes: int = 50 * 1024 * 1024
    docker: str = "docker"


@dataclass(frozen=True)
class ModelLink:
    """The worker's admitted model endpoint for one browse: its loopback port and the token only the
    sidecar's relay holds (Decision 0035 Y7)."""

    port: int
    token: str


@dataclass(frozen=True)
class Stealth:
    """The stealth browser for one session (Decision 0038 Z2, Z3): the workspace's time zone, and
    the challenge hosts its pages may load parts from, which only browser-use is given (Z7)."""

    timezone: str = "UTC"
    challenge_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class BrowserSession:
    name: str
    token: str
    port: int
    run_id: str
    generation: int
    # The browser container's process cap, which says when a count held at it is being enforced.
    pids: int = 256

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
        self,
        run_id: UUID | str,
        generation: int,
        allowed_hosts: tuple[str, ...],
        model: ModelLink | None = None,
        stealth: Stealth | None = None,
    ) -> BrowserSession:
        """`allowed_hosts` are the only hosts the browser may reach, with their subdomains. With
        `model`, the sidecar also relays the box's chat completions to the worker's endpoint. With
        `stealth`, the browser is the stealth one."""
        reachable = allowed_hosts if stealth is None else allowed_hosts + stealth.challenge_hosts
        for host in reachable:
            if not host or any(mark in host for mark in "/, \t") or host.startswith("."):
                raise ExecutorUnavailable("allowed_host_malformed")
        name = f"autobots-browser-{secrets.token_hex(6)}"
        token = secrets.token_urlsafe(24)
        labels = self._labels(name, run_id, generation)
        hardening = self._hardening()
        pids = self.config.pids if stealth is None else self.config.stealth_pids
        try:
            await self._docker("network", "create", "--internal", *labels, f"{name}-net")
            # The proxy's own way out, a network of its own so Docker's DNS finds the browser.
            await self._docker("network", "create", *labels, f"{name}-out")
            # The relay reaches the worker's loopback endpoint through Docker's host gateway.
            relay = (
                [
                    "--add-host", "host.docker.internal:host-gateway",
                    "-e", f"AUTOBOTS_MODEL_UPSTREAM=host.docker.internal:{model.port}",
                    "-e", f"AUTOBOTS_MODEL_TOKEN={model.token}",
                ]
                if model is not None
                else []
            )  # fmt: skip
            await self._docker(
                "run", "-d", "--name", f"{name}-proxy", *labels, *hardening,
                "--network", f"{name}-out",
                "--publish", "127.0.0.1::9223",
                "--memory", "256m", "--cpus", "0.5",
                *relay,
                "-e", f"AUTOBOTS_CDP_TOKEN={token}",
                "-e", f"AUTOBOTS_BROWSER_HOST={name}-browser",
                "-e", f"AUTOBOTS_MAX_REQUESTS={self.config.max_requests}",
                "-e", f"AUTOBOTS_MAX_BYTES={self.config.max_bytes}",
                "-e", f"AUTOBOTS_ALLOWED_HOSTS={','.join(reachable)}",
                self.config.proxy_image,
            )  # fmt: skip
            await self._docker(
                "network", "connect", "--alias", "proxy", f"{name}-net", f"{name}-proxy"
            )
            await self._docker(
                "run", "-d", "--name", f"{name}-browser", *labels, *self._hardening(pids),
                "--network", f"{name}-net", *self._caps(),
                *([] if stealth is None else ["-e", f"TZ={stealth.timezone}"]),
                self.config.browser_image if stealth is None else self.config.stealth_image,
            )  # fmt: skip
            mapping = (await self._docker("port", f"{name}-proxy", "9223")).split()[0]
            port = int(mapping.rsplit(":", 1)[1])
        except (ExecutorUnavailable, IndexError, ValueError):
            await self.remove(name)
            raise ExecutorUnavailable("executor_start_failed") from None
        session = BrowserSession(name, token, port, str(run_id), generation, pids)
        await self._ready(session)
        return session

    @staticmethod
    def _labels(name: str, run_id: UUID | str, generation: int) -> list[str]:
        return [
            "--label", f"{LABEL}=1",
            "--label", f"{LABEL}.run={run_id}",
            "--label", f"{LABEL}.generation={generation}",
            "--label", f"{LABEL}.session={name}",
        ]  # fmt: skip

    def _hardening(self, pids: int | None = None) -> list[str]:
        return [
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(self.config.pids if pids is None else pids),
        ]  # fmt: skip

    def _caps(self) -> list[str]:
        """BX-01's caps and the writable `tmpfs`, for the browser and the browser-use container."""
        return [
            "--tmpfs", f"/tmp:rw,size={self.config.tmpfs},mode=1777",
            "--memory", self.config.memory, "--memory-swap", self.config.memory,
            "--cpus", self.config.cpus,
            "-e", "HOME=/tmp",
        ]  # fmt: skip

    async def run_browser_use(
        self, session: BrowserSession, spec: dict[str, Any], seconds: float
    ) -> str:
        """One browse on browser-use in the session's box, Decision 0035 Y5 and Y8: a container on
        the session's internal network only, driving its Chromium over CDP at the browser's address
        (Chromium refuses a host name in the Host header), with the relay as its model. Returns the
        runner's standard output, untrusted, or "" when it didn't finish within `seconds`. Its
        standard error, which echoes model-written code, is dropped."""
        network = f"{session.name}-net"
        address = (
            await self._docker(
                "inspect", "--format",
                f'{{{{(index .NetworkSettings.Networks "{network}").IPAddress}}}}',
                f"{session.name}-browser",
            )
        ).strip()  # fmt: skip
        if not address:
            raise ExecutorUnavailable("browser_address_missing")
        body = {**spec, "cdp_url": f"http://{address}:{DEVTOOLS_PORT}", "base_url": RELAY_URL}
        code, out, _ = await self._run(
            "run", "--rm", "--name", f"{session.name}-use",
            *self._labels(session.name, session.run_id, session.generation), *self._hardening(),
            "--network", network, *self._caps(),
            "-e", f"AUTOBOTS_BROWSE_SPEC={json.dumps(body)}",
            self.config.browser_use_image,
            seconds=seconds,
        )  # fmt: skip
        if code == -1:
            await self._docker("rm", "-f", f"{session.name}-use", check=False)
            return ""
        return out.decode(errors="replace")

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
        await self._docker(
            "rm", "-f", f"{name}-use", f"{name}-browser", f"{name}-proxy", check=False
        )  # fmt: skip
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
        if code == 0 and count.isdigit() and int(count) >= session.pids - 1:
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
