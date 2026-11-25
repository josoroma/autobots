"""US-20.4, Decision 0038 Z15: the owner's scoreboard, with scripted openings. Nothing here starts a container, opens a
socket or calls a model.
"""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import browser_scoreboard as scoreboard  # noqa: E402
from browser_scoreboard import Opening  # noqa: E402
from qualification.profiles import PROFILES  # noqa: E402

SECRET = 'https://shop.test/private/path?token=abc#part'


class Scoreboard(unittest.TestCase):
    def run_scores(self, openings: dict[str, object], addresses: list[str]) -> tuple[list[scoreboard.Score], list[tuple[str, str]]]:
        asked: list[tuple[str, str]] = []

        async def opener(url: str, browser: str) -> Opening:
            asked.append((url, browser))
            opening = openings[url]
            if isinstance(opening, Exception):
                raise opening
            assert isinstance(opening, Opening)
            return opening

        with contextlib.redirect_stderr(io.StringIO()):
            return asyncio.run(scoreboard.scores(addresses, opener)), asked

    def test_each_address_is_opened_once_in_each_browser(self) -> None:
        addresses = ['https://example.com/', 'https://example.org/']
        found, asked = self.run_scores(dict.fromkeys(addresses, Opening(200, False, 1256)), addresses)
        self.assertEqual(asked, [(address, browser) for address in addresses for browser in ('box', 'stealth')])
        self.assertEqual([(s.host, s.browser, s.result, s.status, s.bytes) for s in found],
                         [(host, browser, 'opened', 200, 1256) for host in ('example.com', 'example.org') for browser in ('box', 'stealth')])

    def test_the_four_results(self) -> None:
        for opening, result in ((Opening(200, False, 9), 'opened'), (Opening(301, False, 0), 'opened'), (Opening(200, True, 9), 'check'),
                                (Opening(403, True, 9), 'check'), (Opening(403, False, 9), 'blocked'), (Opening(503, False, 9), 'blocked'),
                                (Opening(None, False, 0), 'error'), (Opening(None, True, 0), 'check')):
            with self.subTest(opening):
                self.assertEqual(scoreboard.result_of(opening), result)

    def test_an_opening_that_fails_is_an_error_and_the_rest_go_on(self) -> None:
        found, _ = self.run_scores({'https://a.test/': ConnectionError('gone'), 'https://b.test/': Opening(200, False, 1)},
                                   ['https://a.test/', 'https://b.test/'])
        self.assertEqual([s.result for s in found], ['error', 'error', 'opened', 'opened'])

    def test_it_keeps_and_prints_hosts_only(self) -> None:
        found, _ = self.run_scores({SECRET: Opening(403, False, 9)}, [SECRET])
        kept = json.dumps(scoreboard.report(found)) + scoreboard.table(found)
        self.assertIn('shop.test', kept)
        for part in ('private', 'token', 'abc', 'part'):
            self.assertNotIn(part, kept)
        self.assertEqual(scoreboard.report(found)['model'], 'none')

    def test_it_opens_nothing_without_a_plain_https_address(self) -> None:
        for argv in ([], ['http://example.com/'], ['https://user:pw@example.com/'], ['example.com'], ['file:///etc/hosts'],
                     [f'https://h{n}.test/' for n in range(scoreboard.LIMIT + 1)]):
            with self.subTest(argv), mock.patch.object(scoreboard.subprocess, 'run') as run, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(scoreboard.main(argv), 2)
                run.assert_not_called()

    def test_the_child_gets_nothing_of_the_environment_but_what_docker_needs(self) -> None:
        with mock.patch.object(scoreboard.subprocess, 'run') as run, mock.patch.dict(
                scoreboard.os.environ, {'OPENROUTER_API_KEY': 'sk-or-fake', 'AUTOBOTS_DATABASE_URL': 'postgresql://x'}), \
                mock.patch.object(scoreboard, 'PYTHON', Path(sys.executable)):
            run.return_value.returncode = 0
            self.assertEqual(scoreboard.main(['https://example.com/', 'https://example.com/']), 0)
        argv, env = run.call_args.args[0], run.call_args.kwargs['env']
        self.assertEqual(argv[2:], ['https://example.com/'])
        self.assertNotIn('OPENROUTER_API_KEY', env)
        self.assertNotIn('AUTOBOTS_DATABASE_URL', env)

    def test_no_verification_profile_runs_it(self) -> None:
        for profile in PROFILES.values():
            self.assertFalse([script for script in profile.scripts if 'scoreboard' in script], profile.id)
        source = (ROOT / 'scripts/browser_scoreboard.py').read_text()
        self.assertNotIn('openrouter', source.lower())


if __name__ == '__main__':
    unittest.main()
