"""What the isolated browser executor's live qualification binds: US-14.13, PRD-Tool-Catalog BX-05
and Decision 0018 B8.

The executor reports qualified only from a passing live report whose fingerprint is today's, and
only while both images it starts carry that fingerprint's digest in their `autobots.fingerprint`
label. An edit without a rebuild, or a rebuild without a new qualification, turns browsing off
(refactor plan R-57, SQLI-02). Standard library only, so `scripts/browser_images.py` labels each
build with this same digest.
"""

import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

ADAPTERS = "services/agent/src/autobots/adapters"
FINGERPRINT_LABEL = "autobots.fingerprint"
QUALIFICATION = Path(".checks/browser-executor/qualification.json")
# Only what the Docker CLI needs to find its engine. Nothing else of the process reaches it.
DOCKER_ENV_NAMES = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG")
# One line per image, in the order named; Docker exits non-zero if any image is missing.
INSPECT_LABELS = ("image", "inspect", "--format", "{{json .Config.Labels}}")
# A read of two local images, bounded, since it runs synchronously wherever qualification is asked.
INSPECT_SECONDS = 5.0


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

# Every file the images are built from and every module the live check exercises, named one by one,
# so that no file joins or leaves the binding unnoticed (PADP-14).
FINGERPRINTED = (
    BROWSER.dockerfile,
    BROWSER.ignore_file,
    "infra/browser/browser-entrypoint.js",
    PROXY.dockerfile,
    PROXY.ignore_file,
    f"{ADAPTERS}/egress_proxy.py",
    # The Docker session, and the lease checks that end one.
    f"{ADAPTERS}/browser_executor.py",
    f"{ADAPTERS}/browser_cdp.py",
    f"{ADAPTERS}/browser_qualification.py",
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

# Each tag's fingerprint label, or None when the image or its label is missing.
LabelReader = Callable[[tuple[str, ...]], Mapping[str, str | None]]


def images_fingerprint(root: Path) -> dict[str, str]:
    """Each fingerprinted file's SHA-256, by its path from the repository root."""
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in FINGERPRINTED}


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


def images_match(fingerprint: Mapping[str, str], labels: LabelReader = image_labels) -> bool:
    """Both images the executor starts were built from the sources this fingerprint names."""
    expected = fingerprint_digest(fingerprint)
    found = labels(tuple(image.tag for image in IMAGES))
    return all(found.get(image.tag) == expected for image in IMAGES)


def executor_qualified(
    root: Path, report: Path = QUALIFICATION, labels: LabelReader = image_labels
) -> bool:
    """Only after a passing live check at today's fingerprint, and while both images carry it.

    The images are inspected last, so a missing or stale report never reaches Docker.
    """
    try:
        data = json.loads((root / report).read_text())
        fingerprint = images_fingerprint(root)
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
        and all(case in passed for case in REQUIRED_CASES)
        and data.get("executor_fingerprint") == fingerprint
        and images_match(fingerprint, labels)
    )
