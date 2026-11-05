# US-1.8 — H1 independent baseline review and exercised runbook

Status: COMPLETE
Evidence: gate-0

## Plan

- **Source:** [US-1.8](../../../SPECS.md#us-18-h1-independent-baseline-review-and-exercised-runbook), SP-002, SP-003, SP-021, H1.3, DH-A01–16.
- **Intended behavior and invariants:** an independent reviewer inspects the portable baseline, required findings are resolved, the runbook is exercised with a failure and recovery, and a redacted report states real results. No H1 claim beyond what ran. Claude event delivery is not claimed.
- **Affected layers, contracts and states:** the verifier, evidence validator, disposable wrappers, hook dispatcher, fixtures and runbook. No product behavior.
- **Migration and operational impact:** none. Only disposable Docker projects, removed afterwards.
- **Verification and recovery plan:** `harness`, `fast`, `full` and `db` on final inputs, then stale-lock and killed-run recovery, and arranged adapter states.

## Implementation

- **Revision and changed paths:** on top of `b94727d`: `scripts/verify.py`, `harness_lib.py`, `evidence.py`, `disposable_db.py`, `qualify_faults.py`, `.claude/hooks/dispatch.py`, `tests/db/`, `tests/harness/`, `tests/toolchain/test_scaffold_scope.py`, the templates, the evidence contract and the runbook.
- **Actual behavior:** `fast` scope and the `Stop` hook read what differs from the last passing report, not Git. Skips fail a profile. Evidence checks cite a report that `validate` re-reads, or a labeled manual run with an available hashed artifact. Each step's class and transport come from the verifier. The stub worker fixture covers DH-A09.
- **Contract, migration and configuration changes:** new `fault_qualification`, `toolchain_scope_tests` and `disposable_qualification` steps. `.claude/autobots.json` lists `db` as implemented. No product contract or migration.
- **Stubs, deferred work and deviations from the plan:** the worker, state and contract fixtures are synthetic. See [the summary](../evidence/US-1.8/summary.md) for limits.

## Review

- **Author and reviewer:** the main delivery session; `autobots-reviewer` in a separate read-only context, three rounds in the same context, so independent of the author but not fresh.
- **Reviewed fingerprint:** recorded in the [manifest](../evidence/US-1.8/gate-0.json). The reviewer cannot compute hashes, so the coordinator bound it to the final inputs the reviewer read.
- **Findings and dispositions:** [round 1](../evidence/US-1.8/review-r1.md), [round 2](../evidence/US-1.8/review-r2.md) and [round 3](../evidence/US-1.8/review-r3.md), with dispositions in [the summary](../evidence/US-1.8/summary.md).

## Verification

- **Classes and model transport:** static, mock and disposable, with model transport `none` or `mock`. Nothing is `live`.
- **Failures, errors, skips and limits:** in [the summary](../evidence/US-1.8/summary.md), including one self-inflicted hook lockout.

## Runbook

- **Procedure:** [the harness runbook](../runbooks/development-harness.md).
- **Last exercised:** 2026-11-05, on this change's final inputs, on top of `b94727d`. All listed results passed. See the summary.
- **Untested steps:** the forward ingestion section was last exercised in [US-1.2](../evidence/US-1.2/summary.md) and is unchanged. The `operations` profile does not exist.
