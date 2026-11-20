"""Refactor plan R-57 (SQLI-02, SQLI-20): one build entry point for the browser executor's images, each
labelled with the fingerprint of its sources; a qualifier that refuses images built from other sources; and
an entrypoint that names why Chromium didn't start.

Nothing here builds, pulls or runs an image. A fake `docker` on PATH answers and records each call, and the
entrypoint runs under Node with its file system, process and socket calls stubbed, so it never starts
Chromium or listens on a port.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import browser_images  # noqa: E402
import qualify_browser_executor  # noqa: E402
import toolchain  # noqa: E402

SCRIPT = ROOT / 'scripts/browser_images.py'
ENTRYPOINT = ROOT / 'infra/browser/browser-entrypoint.js'
TODAY = browser_images.fingerprint_digest(browser_images.images_fingerprint(ROOT))
OWN = browser_images.fingerprint_digest(browser_images.browser_use_fingerprint(ROOT))
BROWSER, PROXY = browser_images.TAGS
BROWSER_USE = browser_images.BROWSER_USE.tag
# Answers `image inspect` from a file per tag in labels/, records every call with whether the build flag and a
# credential reached it, and refuses anything but an inspect or a build.
FAKE_DOCKER = """#!/bin/sh
here=$(dirname "$0")
printf '%s|buildkit=%s|key=%s\\n' "$*" "${DOCKER_BUILDKIT-unset}" "${OPENROUTER_API_KEY-unset}" >> "$here/calls"
case "$1 $2" in
  'image inspect') file="$here/labels/$(printf '%s' "$5" | tr ':/' '__')"; [ -f "$file" ] || exit 1; /bin/cat "$file";;
  build*) exit 0;;
  *) exit 64;;
esac
"""


def label(value: str | None) -> str:
    return 'null\n' if value is None else f'{{"{browser_images.FINGERPRINT_LABEL}":"{value}"}}\n'


class FakeDocker:
    def __init__(self, labels: dict[str, str | None]) -> None:
        self.folder = Path(tempfile.mkdtemp(prefix='fake-docker-'))
        (self.folder / 'labels').mkdir()
        for tag, value in labels.items():
            (self.folder / 'labels' / tag.replace(':', '_').replace('/', '_')).write_text(label(value))
        (self.folder / 'docker').write_text(FAKE_DOCKER)
        (self.folder / 'docker').chmod(0o755)

    def path(self) -> str:
        return f'{self.folder}{os.pathsep}/usr/bin{os.pathsep}/bin'

    def calls(self) -> list[str]:
        log = self.folder / 'calls'
        return log.read_text().splitlines() if log.exists() else []

    def run(self, *args: str, path: str | None = None) -> subprocess.CompletedProcess[str]:
        env = {'PATH': self.path() if path is None else path, 'HOME': str(self.folder), 'OPENROUTER_API_KEY': 'sk-or-fake'}
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=env, capture_output=True, text=True, timeout=60,
                              check=False)


class Build(unittest.TestCase):
    def test_make_browser_images_is_the_one_build_entry_point(self) -> None:
        makefile = (ROOT / 'Makefile').read_text()
        recipe = re.search(r'^browser-images:\n((?:\t.*\n)+)', makefile, re.MULTILINE)
        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(recipe.group(1), '\tpython3.12 scripts/browser_images.py build\n')
        phony = re.search(r'^\.PHONY:((?:.*\\\n)*.*)$', makefile, re.MULTILINE)
        assert phony is not None
        self.assertIn('browser-images', phony.group(1).split())
        runbook = (ROOT / 'docs/engineering/runbooks/operations.md').read_text()
        self.assertNotIn('docker build', runbook)
        for command in ('make browser-images', 'python3.12 scripts/browser_images.py check',
                        'python3.12 scripts/qualify_browser_executor.py'):
            self.assertIn(command, runbook)

    def test_each_build_is_labelled_with_the_services_fingerprint_digest(self) -> None:
        commands = browser_images.build_commands(ROOT)
        self.assertEqual(commands, [
            ['docker', 'build', '--label', f'autobots.fingerprint={TODAY}', '--tag', BROWSER,
             '--file', str(ROOT / 'infra/browser/browser.Dockerfile'), str(ROOT / 'infra/browser')],
            ['docker', 'build', '--label', f'autobots.fingerprint={TODAY}', '--tag', PROXY,
             '--file', str(ROOT / 'infra/browser/proxy.Dockerfile'), str(ROOT / 'services/agent/src/autobots/adapters')],
            ['docker', 'build', '--label', f'autobots.fingerprint={OWN}', '--tag', BROWSER_USE,
             '--file', str(ROOT / 'infra/browser/browser-use.Dockerfile'), str(ROOT / 'services/browser-use')],
        ])
        self.assertNotEqual(TODAY, OWN)

    def test_a_source_edit_changes_the_label_the_next_build_carries(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder)
            for name in browser_images.browser_use_fingerprint(ROOT):
                (copy / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, copy / name)
            self.assertIn(f'autobots.fingerprint={TODAY}', browser_images.build_commands(copy)[1])
            proxy = copy / 'services/agent/src/autobots/adapters/egress_proxy.py'
            proxy.write_text(proxy.read_text() + '# an edit without a rebuild\n')
            edited = browser_images.build_commands(copy)
            self.assertNotIn(f'autobots.fingerprint={TODAY}', edited[0])
            self.assertEqual(edited[0][3], edited[1][3])
            self.assertNotIn(f'autobots.fingerprint={OWN}', edited[2])
            runner = copy / 'services/browser-use/runner.py'
            runner.write_text(runner.read_text() + '# an edit to browser-use alone\n')
            again = browser_images.build_commands(copy)
            self.assertEqual(again[0][3], edited[0][3])
            self.assertNotEqual(again[2][3], edited[2][3])

    def test_build_runs_both_builds_with_buildkit_and_no_credential(self) -> None:
        docker = FakeDocker({})
        result = docker.run('build')
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = [' '.join(command[1:]) + '|buildkit=1|key=unset' for command in browser_images.build_commands(ROOT)]
        self.assertEqual(docker.calls(), expected)
        self.assertIn(TODAY, result.stdout)
        self.assertIn('python3.12 scripts/qualify_browser_executor.py', result.stdout)

    def test_each_base_image_is_pinned_by_digest_and_names_its_version(self) -> None:
        browser = (ROOT / 'infra/browser/browser.Dockerfile').read_text()
        proxy = (ROOT / 'infra/browser/proxy.Dockerfile').read_text()
        self.assertIn('Playwright (1.64.1)', browser)
        self.assertRegex(proxy, r'Python 3\.12\.16 \(python:3\.12\.16-slim-bookworm\)')
        for text in (browser, proxy):
            self.assertEqual(len(re.findall(r'(?m)^FROM \S+@sha256:[0-9a-f]{64}$', text)), 1)
        # browser-use's: the same Playwright image, and uv's official image only to copy uv from.
        own = (ROOT / 'infra/browser/browser-use.Dockerfile').read_text()
        bases = re.findall(r'(?m)^FROM (\S+@sha256:[0-9a-f]{64})( AS uv)?$', own)
        self.assertEqual([base for base, _ in bases][1], re.search(r'(?m)^FROM (\S+)$', browser).group(1))  # type: ignore[union-attr]
        self.assertTrue(bases[0][0].startswith('ghcr.io/astral-sh/uv@sha256:') and bases[0][1] == ' AS uv')


class Check(unittest.TestCase):
    def test_check_passes_only_when_both_images_carry_todays_fingerprint(self) -> None:
        docker = FakeDocker({BROWSER: TODAY, PROXY: TODAY})
        result = docker.run('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'autobots.fingerprint={TODAY}', result.stdout)
        self.assertFalse([call for call in docker.calls() if call.startswith('build')])

    def test_check_names_each_stale_or_missing_image_and_builds_nothing(self) -> None:
        for labels, named in (({BROWSER: TODAY, PROXY: '0' * 64}, f'{PROXY}: built from other sources'),
                              ({BROWSER: TODAY, PROXY: None}, f'{PROXY}: built from other sources'),
                              ({BROWSER: TODAY}, f'{PROXY}: not built')):
            with self.subTest(named):
                docker = FakeDocker(labels)
                result = docker.run('check')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(named, result.stdout)
                self.assertIn(f'{BROWSER}: current', result.stdout)
                self.assertIn('make browser-images', result.stdout)
                self.assertFalse([call for call in docker.calls() if call.startswith('build')])

    def test_without_browser_uses_image_check_passes_and_says_browsing_stays_on_the_loop(self) -> None:
        docker = FakeDocker({BROWSER: TODAY, PROXY: TODAY})
        result = docker.run('check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'{BROWSER_USE}: not built, so browse_goal stays on the loop', result.stdout)

    def test_a_stale_browser_use_image_fails_check(self) -> None:
        for value in ('0' * 64, TODAY):
            with self.subTest(value):
                docker = FakeDocker({BROWSER: TODAY, PROXY: TODAY, BROWSER_USE: value})
                result = docker.run('check')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f'{BROWSER_USE}: built from other sources', result.stdout)
        docker = FakeDocker({BROWSER: TODAY, PROXY: TODAY, BROWSER_USE: OWN})
        self.assertEqual(docker.run('check').returncode, 0)

    def test_without_docker_check_is_unavailable(self) -> None:
        docker = FakeDocker({})
        empty = tempfile.mkdtemp(prefix='no-docker-')
        result = docker.run('check', path=empty)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn('docker', result.stderr)


class Qualifier(unittest.TestCase):
    def qualify(self, labels: dict[str, str | None]) -> Exception:
        docker = FakeDocker(labels)
        stop = AssertionError('the qualifier went past its image check')
        with mock.patch.dict(os.environ, {'PATH': docker.path()}), \
                mock.patch.object(qualify_browser_executor, 'free_port', side_effect=stop) as free_port, \
                self.assertRaises(Exception) as raised:
            qualify_browser_executor.qualify(ROOT)
        self.assertFalse([call for call in docker.calls() if not call.startswith('image inspect')])
        self.assertEqual(free_port.call_count, 0 if raised.exception is not stop else 1)
        return raised.exception

    def test_the_qualifier_refuses_images_built_from_other_sources_before_anything_starts(self) -> None:
        for labels in ({BROWSER: TODAY, PROXY: '0' * 64}, {BROWSER: None, PROXY: TODAY}, {PROXY: TODAY}):
            with self.subTest(labels):
                refused = self.qualify(labels)
                self.assertIsInstance(refused, qualify_browser_executor.Unavailable)
                self.assertIn('make browser-images', str(refused))

    def test_the_qualifier_goes_on_with_images_built_from_todays_sources(self) -> None:
        self.assertIsInstance(self.qualify({BROWSER: TODAY, PROXY: TODAY}), AssertionError)

    def test_the_report_binds_the_service_fingerprint(self) -> None:
        self.assertEqual(qualify_browser_executor.executor_fingerprint(ROOT), browser_images.images_fingerprint(ROOT))
        self.assertEqual(qualify_browser_executor.IMAGES, (BROWSER, PROXY))


# Stubs Node's file system, process and socket calls for one failure. Nothing listens and nothing is spawned.
PRELOAD = """
"use strict";
const fs = require("node:fs");
const net = require("node:net");
const childProcess = require("node:child_process");
const { EventEmitter } = require("node:events");
const failure = process.env.ENTRYPOINT_FAILURE;
const layout = {
  "/ms-playwright": failure === "no_chromium" ? ["ffmpeg-1011"] : ["ffmpeg-1011", "chromium-1200"],
  "/ms-playwright/chromium-1200": failure === "no_platform" ? ["chrome-mac"] : ["chrome-linux"],
};
fs.readdirSync = (folder) => {
  if (failure === "no_folder" || !(folder in layout)) {
    throw Object.assign(new Error(`ENOENT: no such file or directory, scandir '${folder}'`), { code: "ENOENT" });
  }
  return layout[folder];
};
childProcess.spawn = () => {
  const child = Object.assign(new EventEmitter(), { kill() {} });
  if (failure === "spawn") {
    process.nextTick(() => child.emit("error", Object.assign(new Error("spawn chrome EACCES"), { code: "EACCES" })));
  }
  return child;
};
net.Server.prototype.listen = function listen() {
  if (failure === "listen") {
    process.nextTick(() => this.emit("error", Object.assign(new Error("listen EADDRINUSE: 0.0.0.0:9222"), { code: "EADDRINUSE" })));
  }
  return this;
};
"""


class Entrypoint(unittest.TestCase):
    def setUp(self) -> None:
        try:
            pins = toolchain.read_pins(ROOT)
            self.node = toolchain.find_pinned('node', pins.node, [Path.home() / '.nvm/versions/node' / f'v{pins.node}/bin'])
        except toolchain.Unavailable as missing:
            self.skipTest(str(missing))
        folder = Path(tempfile.mkdtemp(prefix='entrypoint-'))
        self.preload = folder / 'stubs.js'
        self.preload.write_text(PRELOAD)

    def start(self, failure: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([self.node, '--require', str(self.preload), str(ENTRYPOINT)], cwd=self.preload.parent,
                              env={'ENTRYPOINT_FAILURE': failure, 'PATH': '/usr/bin:/bin'}, capture_output=True,
                              text=True, timeout=30, check=False)

    def test_the_stubs_alone_let_the_entrypoint_start(self) -> None:
        result = self.start('none')
        self.assertEqual((result.returncode, result.stderr), (0, ''))

    def test_each_failure_to_find_or_start_chromium_exits_with_one_line(self) -> None:
        for failure, cause in (('no_folder', '/ms-playwright'), ('no_chromium', 'chromium-'),
                               ('no_platform', 'chrome-linux'), ('spawn', 'EACCES'), ('listen', 'EADDRINUSE')):
            with self.subTest(failure):
                result = self.start(failure)
                self.assertEqual(result.returncode, 1, result.stderr)
                lines = result.stderr.splitlines()
                self.assertEqual(len(lines), 1, result.stderr)
                self.assertTrue(lines[0].startswith('browser-entrypoint: '), lines[0])
                self.assertIn(cause, lines[0])


if __name__ == '__main__':
    unittest.main()
