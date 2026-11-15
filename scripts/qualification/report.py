"""The report a disposable qualifier writes when its run ends, in one envelope (SCRP-07, XDUP-13).

The verifier reads only a qualifier's exit code; these files are for people and for recorded evidence, so each
one names its schema, the inputs it saw, its cases and what it doesn't establish.
"""
from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from harness_lib import fingerprint

from qualification.records import Cases, write_report


def finish(root: Path, path: Path, schema: str, cases: Cases, started_at: float, not_established: Sequence[str],
           **extra: object) -> int:
    """Write the report atomically, beside any extra fields such as the project, and return the exit code: 0 when
    every case passed, else 1."""
    write_report(path, {'schema_version': schema, 'completed_at_utc': datetime.now(UTC).isoformat(),
                        'duration_seconds': round(time.monotonic() - started_at, 1), 'input_fingerprint': fingerprint(root),
                        'status': cases.status, 'target_class': 'disposable', **extra, 'cases': cases.records,
                        'not_established': list(not_established)})
    return 0 if cases.status == 'passed' else 1
