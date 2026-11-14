"""R-06: components don't add raw `fetch(` or `csrfFetch(` calls.

Reads and writes move to shared hooks and the typed client (R-27, R-48). Today's callers are the
baseline, which only shrinks: a file that stops calling fetch must leave the list.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = re.compile(r'\b(?:csrfFetch|fetch)\(')
BASELINE = frozenset({
    'components/account-form.tsx',
    'components/approvals-panel.tsx',
    'components/continue-run.tsx',
    'components/data-summary.tsx',
    'components/expert-editor.tsx',
    'components/experts-panel.tsx',
    'components/goal-composer.tsx',
    'components/jobs-chart.tsx',
    'components/keys-and-vars-panel.tsx',
    'components/model-policy-panel.tsx',
    'components/operations-panel.tsx',
    'components/provider-settings-panel.tsx',
    'components/run-controls.tsx',
    'components/run-disclosure.tsx',
    'components/run-panel.tsx',
    'components/run-workspace.tsx',
    'components/session-panel.tsx',
    'components/sign-in-form.tsx',
    'components/sign-out-button.tsx',
    'components/unknown-effects.tsx',
    'components/waiting-notifier.tsx',
    'components/workflow-editor.tsx',
    'components/workflows-panel.tsx',
    'components/workspace-chooser.tsx',
})


def callers(web: Path) -> set[str]:
    return {path.relative_to(web).as_posix() for path in (web / 'components').rglob('*.tsx')
            if RAW.search(path.read_text())}


class RawFetch(unittest.TestCase):
    def test_no_new_component_calls_fetch(self) -> None:
        found = callers(ROOT / 'apps/web')
        self.assertEqual(sorted(found - BASELINE), [], 'use the shared hooks or the typed client')
        self.assertEqual(sorted(BASELINE - found), [], 'these no longer call fetch, so remove them from the baseline')

    def test_a_new_caller_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            web = Path(folder)
            (web / 'components').mkdir()
            (web / 'components/new-panel.tsx').write_text('const reply = await fetch("/api/v1/runs");\n')
            (web / 'components/typed-panel.tsx').write_text('const runs = await listRuns(client);\n')
            self.assertEqual(callers(web), {'components/new-panel.tsx'})


if __name__ == '__main__':
    unittest.main()
