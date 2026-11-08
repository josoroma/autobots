# Verification — us-15-8-model-catalog-facts-binding

Change: us-15-8-model-catalog-facts-binding
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 6 of 6 tasks complete. 1 requirement added to `model-policy-settings`.
- **"Catalog facts apart from qualification":** observed in `python3.12 scripts/verify.py --profile db` (exit 0), in the `models.spec.ts` test "each profile shows catalog prices, capabilities and the fetch time, apart from qualification" (passed). The fixture catalog lists prices and parameters.
  - Terra reads US$1.25 and US$10.00 per 1M tokens, and Sol US$3.00 and US$15.00.
  - The capabilities `max_tokens`, `response_format`, `tool_choice` and `tools` sit under "Capabilities, from the catalog", with no qualification wording among the catalog facts.
  - The fetch time is shown, and `/api/models` returns `fetched_at` within the last two minutes.
  - axe found no violations.
  - Unit test `test_listed_prices_are_per_million_tokens_and_kept_apart_from_the_reserved_rate` shows the listed rates stay apart from the worst-case rate admission reserves.
- **"Where each binding comes from":** observed in the same `db` run. `tests/db/model_sources.py` arranged a policy with no default and a `coder` override, and admitted a run whose direct session's Expert binds the executor to Sol. It used the run route's binding, policy and admission code, without the HTTP key check.
  - The qualification case "a run admitted with a run role override records its sources" observed executor `run_override`, coder `workspace_override` and researcher `builtin_default`.
  - The `models.spec.ts` test "each role says where its binding comes from…" (passed) showed the stored `default_profile` was `null` and the select read Built-in default. Models labels coder "Workspace override", researcher "Built-in default, openai/gpt-6.1-sol-20260929" and planner "Built-in default" on Terra.
  - The run's role map shows executor on Sol "· run override", coder "· workspace override" and researcher on Sol "· built-in default", and axe found no violations.
  - Unit tests cover all four sources, and a run-wide profile reading as a run override. They also cover a snapshot that keeps its sources, and an older snapshot that has none.
  - The workspace-default source is observed in unit tests only, as the arranged workspace names no default.
- **"Discard and Reset all":** observed in `models.spec.ts` "Discard restores the saved form, Reset all clears overrides, and a stale Reset all is refused" (passed).
  - Saving a second override gave `{coder, planner}` and "12 of 14 roles follow the workspace default".
  - Discard after three unsaved edits returned every control to the saved values, left the stored policy unchanged and disabled itself.
  - Reset all sent `expected_version` equal to the saved version. It cleared both overrides, at version+1 with the default kept `null`, and the summary read 14 of 14.
  - Reset all from a screen loaded earlier showed "This policy changed after you opened it, so nothing was reset. Reload the page and try again.", and the stored policy was unchanged.
  - After a reload the summary still read 14 of 14, and axe found no violations.
- **Regression:**
  - `fast` passed (exit 0), after a first run failed on `ruff` line length and format in the new code, since fixed.
  - `full` passed (exit 0, 38 browser tests, including the appearance suites).
  - `db` passed with all 547 identity cases, including the existing settings, slice-policy, saved-choice and slice-run-details specs, now that a missing policy reports `default_profile: null`.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
