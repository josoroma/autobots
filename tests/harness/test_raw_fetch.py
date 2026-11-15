"""R-06, R-48: no raw `fetch(` or `csrfFetch(` call outside the web's transport modules.

Screens, hooks and the run modules call the generated operations through the browser's client,
`lib/api/browser.ts`, so a renamed request field, query or path fails to compile instead of failing
as a 422 (R-48). The modules in TRANSPORT are the only callers, each for the reason it gives, and
any other file under `app/`, `components/` or `lib/` that calls fetch fails here. The hooks beside
a screen (`*.ts`) are scanned too, so a call moved out of the JSX still counts.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = re.compile(r'\b(?:csrfFetch|fetch)\(')
SCANNED = ('app', 'components', 'lib')
TRANSPORT = {
    'lib/api/browser.ts': "the browser's client: its shared reads, its writes and the artifact download",
    'lib/csrf-fetch.ts': 'the double-submit token, and the write it is sent with',
    'lib/bff.ts': "the BFF's forward to the API, on the server",
    'lib/service-status.ts': "the server's own typed reads, with their timeout",
}


def callers(web: Path) -> set[str]:
    """Every file under the scanned folders that calls fetch."""
    return {path.relative_to(web).as_posix() for folder in SCANNED if (web / folder).is_dir()
            for pattern in ('*.tsx', '*.ts') for path in (web / folder).rglob(pattern)
            if RAW.search(path.read_text())}


class RawFetch(unittest.TestCase):
    def test_only_the_transport_calls_fetch(self) -> None:
        found = callers(ROOT / 'apps/web')
        self.assertEqual(sorted(found - set(TRANSPORT)), [],
                         'call a generated operation with the client in lib/api/browser.ts')
        self.assertEqual(sorted(set(TRANSPORT) - found), [],
                         'these no longer call fetch, so remove them from TRANSPORT')

    def test_a_new_caller_is_caught_in_each_folder(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            web = Path(folder)
            for name in ('components', 'lib/runs', 'app/runs'):
                (web / name).mkdir(parents=True)
            (web / 'components/new-panel.tsx').write_text('const reply = await fetch("/api/v1/runs");\n')
            (web / 'components/typed-panel.tsx').write_text('const runs = await listRuns(reads);\n')
            (web / 'lib/runs/new-read.ts').write_text('return csrfFetch(`/api/v1/runs/${id}`, init);\n')
            (web / 'lib/runs/loaded.ts').write_text('return load(readOf(getRun, id));\n')
            (web / 'app/runs/page.tsx').write_text('await fetch("/api/v1/runs");\n')
            self.assertEqual(callers(web), {'components/new-panel.tsx', 'lib/runs/new-read.ts', 'app/runs/page.tsx'})


if __name__ == '__main__':
    unittest.main()
