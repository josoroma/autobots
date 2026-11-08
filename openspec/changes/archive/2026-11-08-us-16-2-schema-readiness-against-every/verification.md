# Verification — us-16-2-schema-readiness-against-every

Change: us-16-2-schema-readiness-against-every
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Scenarios

Each schema state was arranged on the `db` profile's disposable stack as its admin, read by `tests/db/schema_release_check.py` as the runtime role through the real `database_conditions` and `applied_migrations`, then restored. The restore was itself checked: 49 history rows and the hidden table back.

| Scenario | Result | Observed |
|---|---|---|
| Fewer applied migrations is behind | PASS | Newest history row removed: `unavailable schema_behind`, admission stopped (`is_ready` false), applied 48 against shipped 49. Operations' line for that state, "35 of 49 migrations applied.", from `lib/schema-value.ts` in `tests/unit/schema-value.test.ts` |
| All applied is ready | PASS | `ok schema_ready`, applied 49 of 49; in the browser (`operations-values.spec.ts`) Operations read "49 of 49 migrations applied." |
| More applied is ahead, not blocking | PASS | A later history row added: `degraded schema_ahead`, admission not stopped by it (`is_ready` true). The unit test also shows another degraded blocking check still blocks |
| The shipped count can't drift | PASS | `tests/harness/test_app_db.py` (harness profile) and `test_schema_release.py` compare `SHIPPED_MIGRATIONS` and `NEWEST_MIGRATION` with `supabase/migrations`: 49 and `20261108000049_applied_migration_count.sql` |
| Newer objects are required without a history | PASS | History table hidden: `ok schema_ready` with every object present; then `app_private.plan_task_times` (migration 48) hidden too: `unavailable schema_behind`. The four relations and three columns from migrations 38–49 are in the required lists (unit test) |

## Runs

- `python3.12 scripts/verify.py --profile db`: the first run failed one browser case, because `operations-values.spec.ts` lists the allowed value fields and lacked `shipped_migrations`. After adding it: exit 0, 660 cases passed, inputs unchanged during the run.
- After that run, the schema line's wording moved into `lib/schema-value.ts` without changing its text, so it could be unit-tested. `fast` then passed: lint, types, contract drift, web unit tests.
- `python3.12 scripts/verify.py --profile fast` before the db run: exit 0, with ruff, mypy and pytest.

## Findings

None blocking. The browser saw the schema line from the panel before the wording moved to `lib/schema-value.ts`; the next `db` run re-observes it. No independent review, by the delivery rule.
