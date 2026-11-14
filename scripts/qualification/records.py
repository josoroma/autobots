"""The case vocabulary and record shapes the qualifiers write and the verifier and evidence.py read.

Verification classes and model transports are DH-09.2's, which docs/engineering/evidence/README.md
extends with local_runtime (PRD-Development-Harness DH-09.2, SCRP-10). A child check prints ChildCase
records (tests/db/checklib.py); a qualifier records CaseRecord ones through Cases and writes them in a
QualificationReport. Each record keeps the DH-W04 expected-and-observed shape.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal, NotRequired, TypedDict, get_args

from qualification.errors import Unavailable

VerificationClass = Literal['static', 'mock', 'disposable', 'local_runtime', 'live']
ModelTransport = Literal['none', 'mock', 'openrouter_live']
CaseStatus = Literal['passed', 'failed']
CLASSES: frozenset[str] = frozenset(get_args(VerificationClass))
TRANSPORTS: frozenset[str] = frozenset(get_args(ModelTransport))
# What a report keeps of an observation, and what the console line shows of it.
OBSERVED_LIMIT = 400
PRINTED_LIMIT = 140
# What an arrangement's failure shows of the command's stderr.
ARRANGEMENT_STDERR = 200

# `class` is a keyword, so these two use the functional form.
CaseRecord = TypedDict('CaseRecord', {'id': str, 'class': VerificationClass, 'model_transport': ModelTransport,
                                      'expected': str, 'observed': str, 'status': CaseStatus})
StepClass = TypedDict('StepClass', {'class': VerificationClass, 'model_transport': ModelTransport})


class ChildCase(TypedDict):
    """One case a tests/db check printed (tests/db/checklib.py Case)."""

    id: str
    expected: str
    observed: str
    passed: bool


class ChildReport(TypedDict):
    """The JSON line a tests/db check prints last. A check may add fields beside its cases."""

    cases: list[ChildCase]


class QualificationReport(TypedDict):
    """What a qualifier writes under .checks. `status` is passed only when every case passed."""

    schema_version: str
    completed_at_utc: str
    duration_seconds: float
    status: CaseStatus
    target_class: Literal['disposable']
    cases: list[CaseRecord]
    not_established: list[str]
    input_fingerprint: NotRequired[str]
    project: NotRequired[str]
    prior_revision: NotRequired[str]
    digest: NotRequired[str]
    executor_fingerprint: NotRequired[dict[str, str]]
    driver: NotRequired[str]
    network: NotRequired[str]
    model: NotRequired[str]


class Cases:
    """A qualifier's cases, each printed as it is recorded. The class and transport are fixed for the run."""

    def __init__(self, model_transport: ModelTransport = 'none', verification_class: VerificationClass = 'disposable') -> None:
        self.records: list[CaseRecord] = []
        self.model_transport: ModelTransport = model_transport
        self.verification_class: VerificationClass = verification_class

    @property
    def status(self) -> CaseStatus:
        return 'passed' if all(record['status'] == 'passed' for record in self.records) else 'failed'

    def check(self, case_id: str, expected: str, observed: object, passed: object) -> None:
        """Record a case. Any observed value is shown as text, and `passed` is read for its truth."""
        text = str(observed)
        print(f"{'PASS' if passed else 'FAIL'}: {case_id}: {text[:PRINTED_LIMIT]}")
        self.records.append({'id': case_id, 'class': self.verification_class, 'model_transport': self.model_transport,
                             'expected': expected, 'observed': text[:OBSERVED_LIMIT], 'status': 'passed' if passed else 'failed'})

    def denied(self, case_id: str, result: subprocess.CompletedProcess[str], marker: str) -> None:
        self.check(case_id, f'refused with {marker}', (result.stderr or result.stdout).strip()[-140:] or f'exit {result.returncode}',
                   result.returncode != 0 and marker in result.stderr)

    def arranged(self, label: str, expected: str, observed: object, held: bool, *, required: bool = False) -> bool:
        """Record whether an arrangement held, as the case `arranged: <label>`, so a later case cannot pass on a
        fixture that never existed (SCRP-09). A required one that failed raises Unavailable instead, since
        nothing after it would show anything."""
        if required and not held:
            raise Unavailable(f'{label} could not be arranged: {observed}')
        self.check(f'arranged: {label}', expected, observed, held)
        return held

    def arrange(self, label: str, *results: subprocess.CompletedProcess[str], required: bool = False) -> bool:
        """`arranged` for the commands that make an arrangement: it holds when each exited 0."""
        failed = next((result for result in results if result.returncode), None)
        observed = 'exit 0' if failed is None else f'exit {failed.returncode}: {failed.stderr.strip()[-ARRANGEMENT_STDERR:]}'
        return self.arranged(label, 'exit 0', observed, failed is None, required=required)


def write_report(path: Path, report: QualificationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + '\n')
