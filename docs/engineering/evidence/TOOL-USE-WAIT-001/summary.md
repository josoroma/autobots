# TOOL-USE-WAIT-001: a call waiting for approval records its outcome

**Date:** 2026-11-07. **Status:** done. **Scope:** a small fix requested by the user ("Yes, fix it here"), found during US-14.16. Outside the OhMyOrch delivery loop, so this short record follows DH-W01–06.

## Plan

[TU-01](../../../PRD/PRD-Tool-Catalog.md#tool-use-record) says the gateway records every dispatch, denials included, with its outcome.

The gap: a call held for approval returned `approval_pending`, but its tool-use row kept no outcome. The approval gate moves the run to waiting and releases the job's lease. `complete_use` then failed its lease fence and returned without writing.

The fix: complete that one row, and only that row, without the fence.

## Implementation

- `application/tool_uses.py`: `complete_use` takes `fenced` (default `True`). With `fenced=False` it skips `hold_lease`. The update still requires the row's own generation and `outcome is null`.
- `application/tool_gateway.py`: `execute` passes `fenced=False` only when the result's code is `approval_pending`.

Why this is safe: an approval gate reached by a stale worker raises when its fenced transition to waiting fails, so `approval_pending` comes back only to the worker that made that transition. Every other result keeps the fence.

## Review

No independent review ran: the user asked for the fix directly, and no story acceptance requires one.

## Verification

| Check | Exit | Observed |
|---|---|---|
| `tests/db/connector_check.py` on a disposable stack | 0 | 18/18. The new case: the waiting call's row is `('denied', 'approval_pending', finished)`, with exactly 1 `tool.use.completed` event carrying that code. Every existing case, including approval, replay and readback, still passes |
| `python3.12 scripts/verify.py --profile fast` | 0 | passed |
| `python3.12 scripts/verify.py --profile db` | 0 | passed, including `identity_qualification`, which runs the connector check, and `app_db_qualification` |

## Runbook

No operator procedure changed. The run's Tools used list now shows a waiting call as denied `approval_pending`, followed by its approved attempt as a separate row.

## Limits

- Disposable evidence only. Rows already left open on a persistent install aren't backfilled.
- Not H1 or product acceptance.
