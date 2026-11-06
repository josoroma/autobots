# Verification — us-11-8-operations-completeness

Change: us-11-8-operations-completeness
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Show the four missing facts | PASS (arranged) | `scripts/qualify_identity.py`, disposable stack, real browser. The screen shows the arranged routine `missed` on 2026-11-05 with `host away`, `OpenRouter's catalog answered`, `verified, 14 of 14 checks` with its date, and each route's date and own limits. Its text holds no address, path, key shape or ID. The delayed row and the `restores.jsonl` line are arranged. `scripts/qualify_backup.py` shows the real tool writing that record: `not_verified`, then `passed` with counts and no instance name, then `failed` on a failed verification |
| Say what is unknown or unavailable | PASS (arranged) | The fake upstream's catalog is down: the screen says OpenRouter can't be reached and no restore is recorded, still reads ready, and saves retention. Afterward the fake upstream's log holds only `GET /api/v1/key` and `GET /api/v1/models`, so no model call was made |

Checks on the final code: `fast`, `harness` and `qualify_operations.py` exit 0, the identity qualifier's 350 cases and the backup qualifier's 50 pass, and `openspec validate` is clean.

## Findings

None.

## Limits

- **"OpenRouter available" means its public catalog answered.** It says nothing of the key or a model call, and the screen says that.
- **Each load makes one catalog request,** bounded to 3 seconds, so a slow network can delay the page by that much. There's no cache here.
- **Model IDs are shown** beside each route's result, since it can't be read without them. They name public models, and no run, workspace or user ID appears.
- **The restore drill from US-11.3 has no record,** as it ran before this existed. The real install shows none until the next drill.
- **The persistent install wasn't changed or exercised here.**
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
