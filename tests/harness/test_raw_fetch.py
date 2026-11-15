"""R-06: components and the run modules don't add raw `fetch(` or `csrfFetch(` calls.

Reads and writes move to shared hooks and the typed client (R-27, R-48). Today's callers are the
baselines, which only shrink: a file that stops calling fetch must leave its list. `lib/runs/` has
its own, so a call moved out of a run component into the run modules still counts (R-49).
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
    'components/approvals/use-approval-decision.ts',
    'components/composer/use-run-admission.ts',
    'components/data-summary.tsx',
    'components/expert-editor/use-expert-draft.ts',
    'components/experts/use-start-session.ts',
    'components/keys-and-vars/use-item-writes.ts',
    'components/list-detail/use-create-by-name.ts',
    'components/model-policy/use-policy-writes.ts',
    'components/operations/use-retention-save.ts',
    'components/provider-settings/use-provider-writes.ts',
    'components/runs/continue/use-continue-run.ts',
    'components/runs/controls/use-run-controls.ts',
    'components/runs/effects/use-effect-record.ts',
    'components/session-panel.tsx',
    'components/sign-in-form.tsx',
    'components/sign-out-button.tsx',
    'components/waiting-notifier.tsx',
    'components/workflow-editor/use-description.ts',
    'components/workflow-editor/use-graph-draft.ts',
    'components/workflow-editor/use-version-run.ts',
    'components/workspace-chooser.tsx',
})
# The run modules' own requests: the stored result's download and the one run-command POST.
RUN_MODULES_BASELINE = frozenset({
    'lib/runs/commands.ts',
    'lib/runs/published-result.ts',
})


def callers(web: Path, folder: str = 'components') -> set[str]:
    """Every file under `folder` that calls fetch, the hooks beside a screen included (`*.ts`), so
    a call moved out of the JSX into a hook still counts."""
    return {path.relative_to(web).as_posix() for pattern in ('*.tsx', '*.ts')
            for path in (web / folder).rglob(pattern) if RAW.search(path.read_text())}


class RawFetch(unittest.TestCase):
    def test_no_new_component_calls_fetch(self) -> None:
        found = callers(ROOT / 'apps/web')
        self.assertEqual(sorted(found - BASELINE), [], 'use the shared hooks or the typed client')
        self.assertEqual(sorted(BASELINE - found), [], 'these no longer call fetch, so remove them from the baseline')

    def test_no_new_run_module_calls_fetch(self) -> None:
        found = callers(ROOT / 'apps/web', 'lib/runs')
        self.assertEqual(sorted(found - RUN_MODULES_BASELINE), [], 'use the shared hooks or the typed client')
        self.assertEqual(sorted(RUN_MODULES_BASELINE - found), [], 'these no longer call fetch, so remove them from the baseline')

    def test_a_new_caller_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            web = Path(folder)
            (web / 'components').mkdir()
            (web / 'components/new-panel.tsx').write_text('const reply = await fetch("/api/v1/runs");\n')
            (web / 'components/typed-panel.tsx').write_text('const runs = await listRuns(client);\n')
            self.assertEqual(callers(web), {'components/new-panel.tsx'})

    def test_a_new_run_module_caller_is_caught(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            web = Path(folder)
            (web / 'lib/runs').mkdir(parents=True)
            (web / 'lib/runs/new-read.ts').write_text('return csrfFetch(`/api/v1/runs/${id}`, init);\n')
            (web / 'lib/runs/loaded.ts').write_text('return loadJson(path, parseRunList);\n')
            self.assertEqual(callers(web, 'lib/runs'), {'lib/runs/new-read.ts'})


if __name__ == '__main__':
    unittest.main()
