#!/usr/bin/env python3
"""Arrange a disposable copy of the retained forward fixture for the ingestion exercise.

The retained fixture has no `SP-*` requirement, no story-to-story dependency and no story in
progress, so on its own it cannot show those facts survive ingestion. This applies fixed
synthetic edits to a new copy. Nothing here is a claim about the real PRDs or the real backlog.
Run from the repository root. The destination must be new and lie under `.checks`.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / 'docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture'
SPECS_SCRIPT = ROOT / 'scripts/specs.py'

AGENTS_LINE = "This synthetic fixture's backlog stories cite their sources and claim no delivery.\n"
CONTRACT_APPENDIX = '''
## SP-901 Missing-key draft preservation
The backlog must retain a story covering REQ-01.

## SP-902 Retry visibility
The backlog must retain a story covering REQ-03.
'''
PRD_APPENDIX = '''
## REQ-06 Composer autosave
When the composer draft changes, save the current draft automatically using the local storage required by REQ-02. This behavior cannot be delivered until local storage is delivered.
'''
SP_901 = '[CONTRACT.md — SP-901 Missing-key draft preservation](CONTRACT.md#sp-901-missing-key-draft-preservation)'
SP_902 = '[CONTRACT.md — SP-902 Retry visibility](CONTRACT.md#sp-902-retry-visibility)'
COVERAGE = '''**Preserved SP coverage**

| Preserved requirement | Backlog coverage |
|---|---|
| [SP-901](CONTRACT.md#sp-901-missing-key-draft-preservation) | US-1.1 |
| [SP-902](CONTRACT.md#sp-902-retry-visibility) | US-1.3 |

'''
# (anchor, replacement). Each anchor must occur exactly once, or arrangement fails.
SPECS_EDITS = (
    ('The supplied sources contain no `SP-*` identifiers or H0/H1/B phase definitions. '
     'No `AGENTS.md` file exists in this fixture.',
     'The supplied sources define SP-901 and SP-902 and no H0/H1/B phase definitions. '
     'The dependency of US-1.3 on US-1.2 is part of this existing backlog.'),
    ('# EPIC-1: Local Autobots behavior\n\n### US-1.1:',
     COVERAGE + '# EPIC-1: Local Autobots behavior\n\n### US-1.1:'),
    ('- [PRD.md — REQ-01 Missing key](PRD.md#req-01-missing-key)\n',
     f'- [PRD.md — REQ-01 Missing key](PRD.md#req-01-missing-key)\n- {SP_901}\n'),
    ('- [PRD.md — REQ-03 Retry policy](PRD.md#req-03-retry-policy)\n',
     f'- [PRD.md — REQ-03 Retry policy](PRD.md#req-03-retry-policy)\n- {SP_902}\n'),
    ('### US-1.2: Store application records locally\n\nStatus: READY\n',
     '### US-1.2: Store application records locally\n\nStatus: IN PROGRESS\n'
     'Change: `openspec/changes/fixture-us-1-2/`\n'),
    ('Dependencies:\n- None\n\nTasks:\n- [ ] Resolve and record the maximum',
     'Dependencies:\n- US-1.2\n\nTasks:\n- [ ] Resolve and record the maximum'),
)


def checked_destination(destination: Path, root: Path) -> Path:
    resolved = destination.resolve()
    checks = (root / '.checks').resolve()
    if not resolved.is_relative_to(checks) or resolved == checks:
        raise ValueError(f'destination must lie under {checks}')
    if os.path.lexists(resolved):
        raise ValueError(f'destination already exists: {resolved}')
    return resolved


def arrange(destination: Path, *, fixture: Path = FIXTURE, root: Path = ROOT) -> Path:
    """Build the copy beside the destination, so that a failed run leaves no destination."""
    target = checked_destination(destination, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent, prefix='.arranging-') as temporary:
        work = Path(temporary) / 'copy'
        shutil.copytree(fixture, work)
        specs = (work / 'SPECS.md').read_text(encoding='utf-8')
        for anchor, replacement in SPECS_EDITS:
            if specs.count(anchor) != 1:
                raise ValueError(f'fixture anchor not found exactly once: {anchor[:60]!r}')
            specs = specs.replace(anchor, replacement)
        (work / 'SPECS.md').write_text(specs, encoding='utf-8')
        (work / 'AGENTS.md').write_text(AGENTS_LINE, encoding='utf-8')
        for name, appendix in (('CONTRACT.md', CONTRACT_APPENDIX), ('PRD.md', PRD_APPENDIX)):
            path = work / name
            path.write_text(path.read_text(encoding='utf-8') + appendix, encoding='utf-8')
        subprocess.run([sys.executable, str(SPECS_SCRIPT), 'render', '--project-root', str(work),
                        '--path', 'SPECS.md'], check=True, capture_output=True, text=True,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        work.rename(target)
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args(argv)
    try:
        print(arrange(args.destination))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else error
        print(f'ERROR: {detail}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
