## Why

US-1.4 needs one local runner that works without a coding assistant and a thin hook adapter that handles hostile input safely. Today only `harness` runs, its evidence ignores application inputs, and the dispatcher can crash with a traceback on a symlink loop or a broken import.

## What Changes

- `scripts/verify.py` gains `fast` and `full`, built on the toolchain steps from US-1.3. Exit codes: 0 passed, 1 a required check failed, 2 prerequisite unavailable or a check could not run. `db` and `operations` stay `not_implemented`, exit 2.
- `fast` selects Python and web steps by changed paths, conservatively running both for shared or check-infrastructure paths. Unselected steps are recorded `not_run`. `full` runs every step, including the production build.
- Evidence freshness: every report fingerprints application inputs as well. `report_state` reads any profile. `Stop` asks for `fast` or `full` when uncommitted application paths exist.
- `.claude/hooks/dispatch.py`: overall deadline, any internal error exits 2 with a fixed message, unknown tools rejected, bounded paths, secret names checked before and after symlink resolution, `PostToolUse` names affected check domains and runs a bounded `ruff` diagnostic as an argument array.

**Limits, by the sources:** no contract drift or browser fixture exists yet, so neither runs, and the report says so. Domains are derived from the changed path and the fingerprint instead of a stored dirty marker, because the fingerprint already invalidates evidence.

## Capabilities

### New Capabilities

- `portable-verification`: verification profiles with distinct results, and the hook dispatcher's handling of unsafe input.

### Modified Capabilities

None.

## Impact

`scripts/verify.py`, `scripts/harness_lib.py`, `.claude/hooks/dispatch.py`, `.claude/autobots.json`, `tests/harness/`, the harness runbook, `AGENTS.md`, `.claude/rules/delivery.md`, the verify skill and `CODEBASE.md`. No dependency, service, database or model call.
