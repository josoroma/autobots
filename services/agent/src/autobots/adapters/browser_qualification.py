"""What the isolated browser executor's live qualification binds: US-14.13, PRD-Tool-Catalog BX-05
and Decision 0018 B8.

The executor reports qualified only from a passing live report whose fingerprint is today's, and
only while both images it starts carry that fingerprint's digest in their `autobots.fingerprint`
label. An edit without a rebuild, or a rebuild without a new qualification, turns browsing off
(refactor plan R-57, SQLI-02). Standard library only, so `scripts/browser_images.py` labels each
build with this same digest.

browser-use (Decision 0035 Y8) is qualified apart, on top of the executor: its own image, a
fingerprint of the executor's files and its own, its own report and its own cases. Removing its
image turns only browser-use off, which leaves `browse_goal` on Autobots' loop (Decision 0035,
reversal).

The catalog, search, Expert saves and the gateway ask on every read, synchronously. The report and
the sources are read each time, so a withdrawn report or an edited source turns browsing off at
once. The labels need Docker, so one inspect per fingerprint digest is reused for
IMAGE_CHECK_SECONDS: an image rebuilt with another label reads as unqualified within that window,
and a new digest is inspected afresh.
"""

import hashlib
import json
import os
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ADAPTERS = "services/agent/src/autobots/adapters"
APPLICATION = "services/agent/src/autobots/application"
FINGERPRINT_LABEL = "autobots.fingerprint"
QUALIFICATION = Path(".checks/browser-executor/qualification.json")
# Only what the Docker CLI needs to find its engine. Nothing else of the process reaches it.
DOCKER_ENV_NAMES = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")
# One line per image, in the order named; Docker exits non-zero if any image is missing.
INSPECT_LABELS = ("image", "inspect", "--format", "{{json .Config.Labels}}")
# A read of two local images, bounded, since it runs synchronously wherever qualification is asked.
INSPECT_SECONDS = 5.0
# How long one inspect's verdict stands for the same fingerprint digest, so repeated reads start no
# Docker process while a rebuilt image is still seen soon.
IMAGE_CHECK_SECONDS = 30.0


@dataclass(frozen=True)
class Image:
    """One image the executor starts, and what `make browser-images` builds it from."""

    tag: str
    dockerfile: str
    context: str

    @property
    def ignore_file(self) -> str:
        """BuildKit reads `<Dockerfile>.dockerignore` instead of the context's own ignore file."""
        return f"{self.dockerfile}.dockerignore"


BROWSER = Image("autobots-browser:local", "infra/browser/browser.Dockerfile", "infra/browser")
PROXY = Image("autobots-egress:local", "infra/browser/proxy.Dockerfile", ADAPTERS)
IMAGES = (BROWSER, PROXY)
BROWSER_USE = Image(
    "autobots-browser-use:local", "infra/browser/browser-use.Dockerfile", "services/browser-use"
)
BROWSER_USE_QUALIFICATION = Path(".checks/browser-executor/browser-use.json")

# Every file the images are built from and every module the live check exercises, named one by one,
# so that no file joins or leaves the binding unnoticed (PADP-14).
FINGERPRINTED = (
    BROWSER.dockerfile,
    BROWSER.ignore_file,
    "infra/browser/browser-entrypoint.js",
    "infra/browser/chromium-policy.json",
    PROXY.dockerfile,
    PROXY.ignore_file,
    f"{ADAPTERS}/egress_proxy.py",
    # The Docker session, the lease checks that end one, the DevTools client and this binding.
    f"{ADAPTERS}/browser_executor.py",
    f"{APPLICATION}/browser_leases.py",
    f"{ADAPTERS}/browser_cdp.py",
    f"{ADAPTERS}/browser_qualification.py",
)

# browser-use's image sources, and the module that runs it and judges its outcome, on top of the
# executor's own: a change to either needs browser-use qualified again.
BROWSER_USE_FINGERPRINTED = (
    *FINGERPRINTED,
    BROWSER_USE.dockerfile,
    BROWSER_USE.ignore_file,
    "services/browser-use/pyproject.toml",
    "services/browser-use/uv.lock",
    "services/browser-use/runner.py",
    f"{ADAPTERS}/browser_use_box.py",
)

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

# Every case browser-use's live check must observe before it is reported qualified (Decision 0035
# Y8, US-17.3), on top of the executor's own.
REQUIRED_BROWSER_USE_CASES = (
    "a YOLO call runs on browser-use without approval, and with YOLO off it waits for the loop",
    "a browse of the qualification host keeps browse_goal's output",
    "each model request is one admitted call of the run on its researcher route",
    "a navigation outside the allowed domains ends the call refused_action",
    "a navigation the egress proxy refuses ends the call refused_action",
    "a download is refused by Chromium's policy and ends the call refused_action",
    "a page's own refused request is counted and the browse continues",
    "the box reaches only its proxy and its browser",
    "no request reaches Browser Use's hosts",
    "the limits resolve per engine, with a box cap of 600 seconds for browser-use only",
    "a refused model request ends the browse with its code",
    "nothing of the host enters the browser-use container",
    "the session's containers are removed when the call returns",
)

# Each tag's fingerprint label, or None when the image or its label is missing.
LabelReader = Callable[[tuple[str, ...]], Mapping[str, str | None]]


def images_fingerprint(root: Path, names: tuple[str, ...] = FINGERPRINTED) -> dict[str, str]:
    """Each fingerprinted file's SHA-256, by its path from the repository root."""
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def browser_use_fingerprint(root: Path) -> dict[str, str]:
    """The executor's fingerprint with browser-use's own files."""
    return images_fingerprint(root, BROWSER_USE_FINGERPRINTED)


def fingerprint_digest(fingerprint: Mapping[str, str]) -> str:
    """The one value each image's label carries: a digest of the whole fingerprint."""
    return hashlib.sha256(json.dumps(dict(fingerprint), sort_keys=True).encode()).hexdigest()


def parse_labels(output: str, tags: tuple[str, ...]) -> dict[str, str | None]:
    """Each tag's label from `docker image inspect` output printed with INSPECT_LABELS' format."""
    lines = output.splitlines()
    if len(lines) != len(tags):
        return dict.fromkeys(tags)
    found: dict[str, str | None] = {}
    for tag, line in zip(tags, lines, strict=True):
        try:
            labels = json.loads(line)
        except ValueError:
            labels = None
        value = labels.get(FINGERPRINT_LABEL) if isinstance(labels, dict) else None
        found[tag] = value if isinstance(value, str) else None
    return found


def image_labels(
    tags: tuple[str, ...], docker: str = "docker", environ: Mapping[str, str] | None = None
) -> dict[str, str | None]:
    """The local images' labels, by one read-only inspect. Any failure reads as no label."""
    source = os.environ if environ is None else environ
    env = {name: source[name] for name in DOCKER_ENV_NAMES if name in source}
    try:
        completed = subprocess.run(
            [docker, *INSPECT_LABELS, *tags],
            env=env,
            capture_output=True,
            text=True,
            timeout=INSPECT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return dict.fromkeys(tags)
    return parse_labels(completed.stdout if completed.returncode == 0 else "", tags)


def images_match(
    fingerprint: Mapping[str, str],
    labels: LabelReader = image_labels,
    images: tuple[Image, ...] = IMAGES,
) -> bool:
    """Every image named was built from the sources this fingerprint names."""
    expected = fingerprint_digest(fingerprint)
    found = labels(tuple(image.tag for image in images))
    return all(found.get(image.tag) == expected for image in images)


@dataclass(frozen=True)
class _Checked:
    digest: str
    matched: bool
    at: float


class ImageCheck:
    """`images_match` for the process, reusing a verdict for the same digest for `seconds`.

    Thread-safe, so a registry built off the event loop shares it. A failed inspect is reused too,
    so an unreachable Docker isn't asked again on every read.
    """

    def __init__(
        self,
        labels: LabelReader = image_labels,
        seconds: float = IMAGE_CHECK_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        images: tuple[Image, ...] = IMAGES,
    ) -> None:
        self._labels = labels
        self._images = images
        self._seconds = seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._checked: _Checked | None = None

    def matches(self, fingerprint: Mapping[str, str]) -> bool:
        digest = fingerprint_digest(fingerprint)
        with self._lock:
            checked = self._checked
            if (
                checked is not None
                and checked.digest == digest
                and self._clock() - checked.at < self._seconds
            ):
                return checked.matched
            matched = images_match(fingerprint, self._labels, self._images)
            self._checked = _Checked(digest, matched, self._clock())
            return matched


# The ones the service asks through, unless a caller names its own label reader.
IMAGE_CHECK = ImageCheck()
BROWSER_USE_CHECK = ImageCheck(images=(BROWSER_USE,))


def _passing(
    report: Path, required: tuple[str, ...], key: str, fingerprint: Mapping[str, str]
) -> bool:
    """A readable report that passed, observed every required case, and binds this fingerprint."""
    try:
        data = json.loads(report.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    cases = data.get("cases")
    passed = {
        case.get("id")
        for case in (cases if isinstance(cases, list) else [])
        if isinstance(case, dict) and case.get("status") == "passed"
    }
    return (
        data.get("status") == "passed"
        and all(case in passed for case in required)
        and data.get(key) == fingerprint
    )


def executor_qualified(
    root: Path, report: Path = QUALIFICATION, labels: LabelReader | None = None
) -> bool:
    """Only after a passing live check at today's fingerprint, and while both images carry it.

    The images are inspected last, so a missing or stale report never reaches Docker. Without
    `labels`, the process's IMAGE_CHECK reads them; a reader passed in is asked every time.
    """
    try:
        fingerprint = images_fingerprint(root)
    except OSError:
        return False
    if not _passing(root / report, REQUIRED_CASES, "executor_fingerprint", fingerprint):
        return False
    return IMAGE_CHECK.matches(fingerprint) if labels is None else images_match(fingerprint, labels)


def browser_use_qualified(
    root: Path,
    report: Path = BROWSER_USE_QUALIFICATION,
    labels: LabelReader | None = None,
    executor_report: Path = QUALIFICATION,
) -> bool:
    """Decision 0035 Y8 and Y15: only while the executor is qualified, after a passing browser-use
    check at today's browser-use fingerprint, and while its image carries that fingerprint."""
    if not executor_qualified(root, executor_report, labels):
        return False
    try:
        fingerprint = browser_use_fingerprint(root)
    except OSError:
        return False
    if not _passing(
        root / report, REQUIRED_BROWSER_USE_CASES, "browser_use_fingerprint", fingerprint
    ):
        return False
    if labels is None:
        return BROWSER_USE_CHECK.matches(fingerprint)
    return images_match(fingerprint, labels, (BROWSER_USE,))
