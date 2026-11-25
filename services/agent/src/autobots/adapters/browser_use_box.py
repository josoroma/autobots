"""browser-use in the isolated box: the guard on its model requests and its outcome. Decision 0035
Y5 to Y9, Y15 and Y16, and Decision 0018 "a refused action ends the call".

The box's printed report is untrusted data. It supplies the summary text, which is third-party
content anyway, and browser-use's status and steps. What ends a call is decided here from what the
worker observed itself: its CDP log of the box's Chromium (`browser_cdp.RequestGuard`) and the
requests that reach the browse's model endpoint (`model_endpoint`).

- **A refused action the model chose.** A top-frame navigation that landed on an error page, a
  download, or browser-use's own refusal of a host outside the domains or of a `file:` URL. It
  refuses the next model request with `refused_action` before admission, so no step follows.
- **An admission refusal.** Budget, model calls, time or a cancelled run fails the call with its
  code, as `LoopStopped` does on the loop.
- **Bounded spend.** Past `max_steps` plus one delivery turn, the guard refuses with `max_steps`, so
  a box that ignored its limit can't spend more.
- **A bot check (Y10).** A CAPTCHA frame, a challenge page or a "sorry" address the guard saw
  refuses the next request with `bot_check`, which outranks `refused_action`.
- **A check that may clear (Decision 0038 Z8).** On the stealth browser the next request waits,
  before admission, while a page shows a check that needs nobody. One that outlasts its time is a
  bot check.
- **What it saw (Y11).** At each model request, before admission, the worker captures the page
  over its own connection: each step's view as the step began, and where a refused request
  stopped. It is for people only (Y16). browser-use closes its tabs when it stops, so nothing is
  captured after its run.

`browse_in_box` runs one such browse: the worker's model endpoint, the session with its relay, the
worker's own guard and log on the box's Chromium, and the browser-use container. This module is in
browser-use's fingerprint (`browser_qualification.BROWSER_USE_FINGERPRINTED`).
"""

import asyncio
import base64
import binascii
import contextlib
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets

from autobots.adapters.browser_cdp import Cdp, Patience, RequestGuard
from autobots.adapters.browser_executor import (
    BrowserExecutor,
    BrowserSession,
    ExecutorUnavailable,
    ModelLink,
    Stealth,
)
from autobots.adapters.browser_qualification import browser_use_qualified, stealth_qualified
from autobots.adapters.model_endpoint import Answer, EndpointRefused, ModelEndpoint, Reply
from autobots.adapters.model_endpoint import admitted_answer as admitted
from autobots.application.bounded import stop_task
from autobots.application.browsing_loop import BrowseOutcome
from autobots.application.loop_admission import AdmittingLoop
from autobots.application.tool_definitions import ToolFailed
from autobots.contracts.browsing import Stopped, StoppedV3
from autobots.domain.models import ModelRoute

REPOSITORY = Path(__file__).resolve().parents[5]

# browser-use 1.0.6's own notices when its helpers refuse a URL before any request (its domains.py),
# and its notice that a download started. Bound by the pin and observed by the qualification.
REFUSAL_NOTICES = (
    "is not in allowed_domains",
    "is a file: URL or has no host",
    "[download started:",
)
# browser-use's run status, as browse_goal's stop reason. Anything else fails the call.
STOPPED: dict[str, Stopped] = {
    "completed": "done",
    "max_steps": "max_steps",
    "timeout": "max_seconds",
}
# One screenshot per step, for people only: JPEG at this quality keeps a page near 100 KB.
SCREENSHOT = {"format": "jpeg", "quality": 60}
# A step's record: its number, the page it ended on, its screenshot and its submits.
StepSink = Callable[[int, str | None, bytes | None, tuple[str, ...]], Awaitable[None]]
REPORT_TEXT_LIMIT = 20_000
# How long a browse with no outcome of its own waits for the watcher to say why the session ended.
SETTLE_SECONDS = 10.0


def browser_use_ready(root: Path = REPOSITORY) -> bool:
    """Decision 0035 Y8 and Y15: browser-use's own passing check binds today's images."""
    return browser_use_qualified(root)


def stealth_ready(root: Path = REPOSITORY) -> bool:
    """Decision 0038 Z6: the stealth browser's own passing check binds today's image."""
    return stealth_qualified(root)


@dataclass
class BoxWatch:
    """What the worker saw of one browse on browser-use; `refused` and `bot_check` read its log."""

    max_calls: int
    refused: Callable[[], bool]
    bot_check: Callable[[], bool] = lambda: False
    settle: Callable[[], Awaitable[None]] | None = None
    model_calls: int = 0
    requests: int = 0
    stopped: str | None = None
    refusal: str | None = None


def _latest_results(body: Mapping[str, Any]) -> list[str]:
    """The tool results after the request's last assistant message: what the last step returned."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return []
    results: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, Mapping) or message.get("role") == "assistant":
            break
        if message.get("role") == "tool":
            results.append(json.dumps(message.get("content"), ensure_ascii=False))
    return results


def notices_refusal(body: Mapping[str, Any]) -> bool:
    return any(notice in result for result in _latest_results(body) for notice in REFUSAL_NOTICES)


def guarded(
    answer: Answer, watch: BoxWatch, before: Callable[[], Awaitable[None]] | None = None
) -> Answer:
    """`answer` behind the browse's guard, counting the calls it admits. `before` runs ahead of
    each request, refused ones included."""

    async def guarded_answer(body: Mapping[str, Any]) -> Reply:
        watch.requests += 1
        if before is not None:
            await before()
        if watch.stopped is None and watch.settle is not None:
            await watch.settle()
        if watch.stopped is None and watch.bot_check():
            watch.stopped = "bot_check"
        elif watch.stopped is None and (watch.refused() or notices_refusal(body)):
            watch.stopped = "refused_action"
        elif watch.stopped is None and watch.model_calls >= watch.max_calls:
            watch.stopped = "max_steps"
        if watch.stopped is not None:
            raise EndpointRefused(403, watch.stopped, "This browse has ended.")
        try:
            reply = await answer(body)
        except EndpointRefused as refused:
            if refused.status == 403 and watch.refusal is None:
                watch.refusal = refused.code
            raise
        watch.model_calls += 1
        return reply

    return guarded_answer


@dataclass(frozen=True)
class BoxReport:
    """The runner's last JSON line, as untrusted data."""

    status: str
    text: str
    steps: int
    output: Any = None


def parse_report(output: str) -> BoxReport | None:
    """The runner's report: the last line of its output that is a JSON object with a status."""
    for line in reversed(output.strip().splitlines()):
        try:
            data = json.loads(line)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get("status"), str):
            text = data.get("text")
            steps = data.get("steps")
            return BoxReport(
                data["status"],
                text[:REPORT_TEXT_LIMIT] if isinstance(text, str) else "",
                steps if isinstance(steps, int) and steps >= 0 else 0,
                data.get("output"),
            )
    return None


def outcome(
    report: BoxReport | None,
    watch: BoxWatch,
    *,
    refused: bool,
    visited: tuple[str, ...],
    bot_check: bool = False,
    submits: tuple[str, ...] = (),
) -> BrowseOutcome:
    """browse_goal's outcome, or `ToolFailed` with the code that ended the browse."""
    # browser-use counts its delivery turn as a step, so the call's own limit caps what it reports.
    limit = watch.max_calls - 1
    steps = min(report.steps, watch.model_calls, limit) if report is not None else 0
    text = report.text if report is not None else ""

    def ended(stopped: StoppedV3, result: Any = None) -> BrowseOutcome:  # noqa: ANN401 - untrusted JSON
        return BrowseOutcome(text, visited, steps, watch.model_calls, stopped, result, submits)

    if watch.stopped == "bot_check" or bot_check:
        return ended("bot_check")
    if watch.stopped == "refused_action" or refused:
        return ended("refused_action")
    if watch.refusal is not None:
        raise ToolFailed(watch.refusal)
    if watch.stopped == "max_steps":
        return ended("max_steps")
    if report is None or report.status not in STOPPED:
        raise ToolFailed("browser_use_failed")
    return ended(STOPPED[report.status], report.output)


@dataclass(frozen=True)
class BoxModel:
    """The run's admission, its attempt model and the frozen route each request is admitted on."""

    middleware: AdmittingLoop
    model: Any
    route: ModelRoute


@dataclass(frozen=True)
class BoxCall:
    """One browse on browser-use: the call's task, domains and resolved limits, and the seconds past
    its limit the session may last for its start and cleanup."""

    task: str
    start_url: str
    allowed_domains: tuple[str, ...]
    max_steps: int
    max_seconds: int
    grace: int
    output_schema: Mapping[str, Any] | None = None
    # The stealth browser, when the call's Expert is set to it (Decision 0038 Z1).
    stealth: Stealth | None = None

    def spec(self) -> dict[str, Any]:
        spec: dict[str, Any] = {
            "task": self.task,
            "start_url": self.start_url,
            "allowed_domains": list(self.allowed_domains),
            "max_steps": self.max_steps,
            "max_seconds": self.max_seconds,
        }
        if self.stealth is not None:
            spec["stealth"] = True
        if self.output_schema is not None:
            # The worker keeps link fields' queries itself, so the model never sees the extension.
            schema = {k: v for k, v in self.output_schema.items() if k != "x-link-fields"}
            spec["output_schema"] = schema
        return spec


@dataclass
class _Steps:
    """Each step's screenshot and submits, from the worker's own connection to the box's browser."""

    cdp: Cdp
    guard: RequestGuard
    sink: StepSink | None
    taken: int = 0
    submits_seen: int = 0

    async def take(self) -> None:
        if self.sink is None:
            return
        self.taken += 1
        page = self.guard.navigated[-1] if self.guard.navigated else None
        submits = tuple(self.guard.submitted[self.submits_seen :])
        self.submits_seen = len(self.guard.submitted)
        await self.sink(self.taken, page, await self._picture(), submits)

    async def _picture(self) -> bytes | None:
        session = self.guard.latest or next(iter(self.guard.pages), None)
        if session is None:
            return None
        try:
            reply = await self.cdp.send("Page.captureScreenshot", SCREENSHOT, session)
            return base64.b64decode(reply["result"]["data"], validate=True)
        except (
            ConnectionError,
            TimeoutError,
            KeyError,
            TypeError,
            binascii.Error,
            websockets.WebSocketException,
        ):
            return None


def _reason(watcher: "asyncio.Task[str]") -> str | None:
    """Why the watcher removed the session, or None while it runs or if it failed itself."""
    if not watcher.done() or watcher.cancelled() or watcher.exception() is not None:
        return None
    return watcher.result()


async def browse_in_box(
    executor: BrowserExecutor,
    call: BoxCall,
    *,
    start: Callable[[ModelLink], Awaitable[BrowserSession]],
    alive: Callable[[], Awaitable[bool]],
    model: BoxModel,
    visited: Callable[[Sequence[str]], tuple[str, ...]],
    steps: StepSink | None = None,
) -> BrowseOutcome:
    """One browse on browser-use in the session's box, judged from what the worker observed."""
    guards: list[RequestGuard] = []
    recorder: list[_Steps] = []

    async def step_ended() -> None:
        if recorder:
            await recorder[0].take()

    async def settle() -> None:
        for guard in guards:
            await guard.settle()

    watched: dict[str, Any] = (
        {} if call.stealth is None else {"patience": Patience(call.stealth.challenge_hosts)}
    )
    watch = BoxWatch(
        max_calls=call.max_steps + 1,
        refused=lambda: any(g.refusals() for g in guards),
        bot_check=lambda: any(g.bot_checks for g in guards),
        settle=None if call.stealth is None else settle,
    )
    answer = guarded(admitted(model.middleware, model.model, model.route), watch, step_ended)
    async with ModelEndpoint(answer) as endpoint:
        try:
            session = await start(ModelLink(endpoint.port, endpoint.token))
        except ExecutorUnavailable:
            raise ToolFailed("executor_unavailable") from None
        seconds = call.max_seconds + call.grace
        watcher = asyncio.create_task(executor.watch(session, alive, seconds=seconds))
        cdp: Cdp | None = None
        try:
            cdp = await Cdp.connect(await session.websocket_url())
            guard = RequestGuard(cdp, submits=True, **watched)
            await guard.start()
            guards.append(guard)
            recorder.append(_Steps(cdp, guard, steps))
            printed = await executor.run_browser_use(session, call.spec(), seconds=seconds)
            report = parse_report(printed)
            undecided = watch.stopped is None and watch.refusal is None and not guard.refusals()
            if (
                undecided
                and not guard.bot_checks
                and (report is None or report.status not in STOPPED)
            ):
                # A session the watcher ended may still be being removed when the box's run returns,
                # so its reason is read once the watcher settles.
                await asyncio.wait({watcher}, timeout=SETTLE_SECONDS)
                reason = _reason(watcher)
                if reason == "attempt_ended":
                    return BrowseOutcome("", (), 0, watch.model_calls, "cancelled")
                if reason is not None:
                    raise ToolFailed(f"browser_{reason}")
            return outcome(
                report,
                watch,
                refused=guard.refusals() > 0,
                visited=visited(guard.navigated),
                bot_check=bool(guard.bot_checks) or (bool(watched) and bool(guard.checking)),
                submits=tuple(guard.submitted),
            )
        except (ConnectionError, OSError, TimeoutError, websockets.WebSocketException):
            await asyncio.wait({watcher}, timeout=SETTLE_SECONDS)
            reason = _reason(watcher)
            if reason == "attempt_ended":
                return BrowseOutcome("", (), 0, watch.model_calls, "cancelled")
            raise ToolFailed(
                "browser_unreachable" if reason is None else f"browser_{reason}"
            ) from None
        except ExecutorUnavailable:
            raise ToolFailed("executor_unavailable") from None
        finally:
            try:
                if cdp is not None:
                    with contextlib.suppress(Exception):
                        await cdp.close()
                await stop_task(watcher)
            finally:
                # The session stops even when a cancellation lands during the cleanup above.
                await executor.stop(session)
