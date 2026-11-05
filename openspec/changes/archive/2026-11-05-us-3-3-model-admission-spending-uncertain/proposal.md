## Why

Parallel work and retries must not silently overrun a displayed budget, and SP-008, MP-07 and MP-08 require atomic reservation before dispatch, two shared slots, explicit uncertain charges and bounded retries.

## What Changes

- `app_private.model_invocations` and `model_spend_limits`: a private ledger where every attempt is a row, and estimates and reported charges stay separate columns.
- `application/model_admission.py`: slot and cost admission under a workspace advisory lock, shared by a root and its descendants, with UTC day buckets, a warning at 80% and a pause past 100%.
- `application/model_attempts.py`: MP-08's failure classes, at most two retries respecting `Retry-After`, the root deadline and the same model and budget, no redispatch after uncertain acceptance, and no tool execution from incomplete output.

**Limits:** nothing dispatches through this yet, since the worker and graph stories call it. Mapping the real SDK's streaming failures to these classes is only partly exercised, and live behavior belongs to US-3.4. A crashed worker's held slot needs the leases of US-4.2.

## Capabilities

### New Capabilities

- `model-admission`: budget and slot admission, uncertain attempts and bounded retries.

### Modified Capabilities

None.

## Impact

A migration, two application modules, `scripts/app_db.py`, tests and `CODEBASE.md`. No dependency, paid call or persistent change.
