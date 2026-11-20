#!/usr/bin/env python3
"""Build the isolated browser executor's two images and browser-use's, each labelled with the fingerprint of
its sources (refactor plan R-57, SQLI-02; Decision 0018 B1 and B3; Decision 0035 Y8).

`build` runs `docker build` for each image, from the Dockerfile and context the service's `browser_qualification`
module names, with `--label autobots.fingerprint=<digest>`. The executor's two carry the executor's digest, and
browser-use's carries its own. Each Dockerfile's own `<Dockerfile>.dockerignore` narrows its context to the files
it copies. The bases are pinned by digest, so a build pulls each one only if it is absent. `check` reads the labels
with `docker image inspect` and changes nothing.

The executor reports qualified only while both its labels equal today's digest and a passing live report from
scripts/qualify_browser_executor.py carries the same fingerprint; browser-use, likewise with its own. Without the
browser-use image, browse_goal stays on Autobots' loop (Decision 0035, reversal), so `check` reports it and still
passes. In no verification profile: a check never builds an image.

Exit codes: 0 built, or the executor's images current and browser-use's current or not built; 1 a build failed, or
an image is missing or built from other sources; 2 Docker is unavailable.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from disposable_db import Unavailable, run, tool_env
from harness_lib import project_root

sys.path.insert(0, str(project_root() / 'services/agent/src'))
# Standard library only, so this interpreter imports it without the service's environment.
from autobots.adapters.browser_qualification import (
    BROWSER_USE,
    FINGERPRINT_LABEL,
    IMAGES,
    INSPECT_LABELS,
    Image,
    browser_use_fingerprint,
    fingerprint_digest,
    images_fingerprint,
    parse_labels,
)

# The executor's images, which both qualifiers require; browser-use's is optional (Decision 0035, reversal).
TAGS = tuple(image.tag for image in IMAGES)
# A first build pulls both bases; later ones reuse the layer cache.
BUILD_TIMEOUT = 1800.0
REBUILD = 'build them with `make browser-images`'
REQUALIFY = 'python3.12 scripts/qualify_browser_executor.py'
DESCRIBED = {'current': 'current', 'stale': 'built from other sources', 'missing': 'not built'}


def _build(root: Path, image: Image, digest: str) -> list[str]:
    return ['docker', 'build', '--label', f'{FINGERPRINT_LABEL}={digest}', '--tag', image.tag,
            '--file', str(root / image.dockerfile), str(root / image.context)]


def build_commands(root: Path) -> list[list[str]]:
    """One `docker build` per image: the executor's labelled with its digest, browser-use's with its own."""
    executor = fingerprint_digest(images_fingerprint(root))
    own = fingerprint_digest(browser_use_fingerprint(root))
    return [*(_build(root, image, executor) for image in IMAGES), _build(root, BROWSER_USE, own)]


def _state(tag: str, expected: str) -> str:
    inspected = run(['docker', *INSPECT_LABELS, tag], tool_env())
    if inspected.returncode:
        return 'missing'
    return 'current' if parse_labels(inspected.stdout, (tag,))[tag] == expected else 'stale'


def image_states(fingerprint: dict[str, str]) -> dict[str, str]:
    """'current', 'stale' or 'missing' for each image the executor starts, by read-only inspects."""
    expected = fingerprint_digest(fingerprint)
    return {tag: _state(tag, expected) for tag in TAGS}


def browser_use_state(root: Path) -> str:
    """The browser-use image's state against its own fingerprint."""
    return _state(BROWSER_USE.tag, fingerprint_digest(browser_use_fingerprint(root)))


def require_current_images(fingerprint: dict[str, str]) -> None:
    """Raises Unavailable naming each image that is missing or was built from other sources."""
    wrong = [f'{tag} is {DESCRIBED[state]}' for tag, state in image_states(fingerprint).items() if state != 'current']
    if wrong:
        raise Unavailable(f"{'; '.join(wrong)}: {REBUILD}")


def build(root: Path) -> int:
    commands = build_commands(root)
    env = {**tool_env(), 'DOCKER_BUILDKIT': '1'}
    for command in commands:
        tag = command[command.index('--tag') + 1]
        print(f'Building {tag}.', flush=True)
        try:
            built = subprocess.run(command, env=env, timeout=BUILD_TIMEOUT, check=False)
        except FileNotFoundError as error:
            raise Unavailable('docker is not installed; nothing was installed') from error
        except subprocess.TimeoutExpired as error:
            raise Unavailable(f'building {tag} timed out after {BUILD_TIMEOUT:.0f} seconds') from error
        if built.returncode:
            print(f'FAIL: {tag} did not build (docker exit code {built.returncode}).', file=sys.stderr)
            return 1
    label = commands[0][commands[0].index('--label') + 1]
    own = commands[-1][commands[-1].index('--label') + 1]
    print(f"Built {' and '.join(TAGS)} with {label}, and {BROWSER_USE.tag} with {own}. "
          f"Requalify the executor and browser-use with: {REQUALIFY}")
    return 0


def check(root: Path) -> int:
    fingerprint = images_fingerprint(root)
    states = image_states(fingerprint)
    for tag, state in states.items():
        print(f'{tag}: {DESCRIBED[state]}')
    own = browser_use_state(root)
    print(f"{BROWSER_USE.tag}: {DESCRIBED[own]}" + (', so browse_goal stays on the loop' if own == 'missing' else ''))
    if all(state == 'current' for state in states.values()) and own != 'stale':
        print(f'PASS: the executor\'s images carry {FINGERPRINT_LABEL}={fingerprint_digest(fingerprint)}.')
        return 0
    print(f'FAIL: {REBUILD}, then requalify with: {REQUALIFY}')
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description='Build or check the browser executor images.')
    parser.add_argument('command', choices=('build', 'check'))
    command = parser.parse_args(argv).command
    try:
        return build(project_root()) if command == 'build' else check(project_root())
    except Unavailable as error:
        print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
