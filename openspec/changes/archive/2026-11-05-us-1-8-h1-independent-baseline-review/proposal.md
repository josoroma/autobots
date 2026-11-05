## Why

Gate 0 needs the portable baseline independently reviewed, its runbook exercised, including a failure and recovery, and a redacted report of real results before feature work starts. SP-002, H1.3 and DH-A01–16 require this. It is the one EPIC-1 story whose own acceptance asks for an independent review, so Decision 0003 does not remove it.

## What Changes

- A separate read-only `autobots-reviewer` context reviews the baseline. Its findings, and what was done about them, are recorded.
- `tests/db/worker_fixture.sql` and `worker_cases` add the stub worker crash, duplicate and lease-expiry fixtures that DH-A09 asks for, which no earlier story covered.
- `scripts/evidence.py record` derives manifest checks from verifier reports, closing the hand-written gap US-1.5 reported.
- A real DH-W01–06 record: `docs/engineering/work-items/US-1.8.md` and `docs/engineering/evidence/US-1.8/`, with a Gate 0 table for DH-A01–16.

**Limits:** Gate 0 is reported gate by gate, not as a blanket pass. Claude event delivery stays unqualified. The adapter's incompatible state is arranged, because the real client meets the minimum version.

## Capabilities

### New Capabilities

- `baseline-gate-review`: reviewed findings, an exercised runbook and honest adapter reporting.

### Modified Capabilities

None.

## Impact

`scripts/disposable_db.py`, `scripts/evidence.py`, `tests/db/`, `tests/harness/`, the harness runbook, `CODEBASE.md`, and new records under `docs/engineering/`. No dependency, paid call or persistent change.
