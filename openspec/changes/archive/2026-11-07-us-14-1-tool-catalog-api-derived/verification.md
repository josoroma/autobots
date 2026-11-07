# Verification — us-14-1-tool-catalog-api-derived

Change: us-14-1-tool-catalog-api-derived
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 5/5 tasks, 3 reqs |
| Correctness | 3/3 reqs covered, each scenario observed in process and the first also through the BFF in a browser run |
| Coherence | Followed the proposal. No design.md: one layer, no migration |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| The catalog matches the registry | PASS | `tests/test_tool_catalog.py`: the registered `(tool_id, version)` pairs of the worker's registry equal the catalog's registered entries, each once; the only unregistered entry is `browse_goal`, `disabled_by_policy` with no grant site; every tool's schemas, class, limits and input fields match its definition. Through the BFF: `apps/web/tests/browser/boundary.spec.ts` "US-14.1", run by `scripts/qualify_web.py` against the real API app with an arranged membership, reads `/api/v1/tools` as a member (200, schema version 1, a 64-hex digest, unique IDs, `browse_goal` disabled, `create_github_issue` naming its two variables and reading `key_missing` in that reduced environment) and one version by `/api/v1/tools/calculate/versions/1`. No session is refused 401 and another workspace's member 403 |
| Discovery doesn't grant | PASS | `test_discovery_does_not_grant`: a scope granting only `calculate` shows the model only `calculate`, while the catalog lists `read_run_file`; a call to `read_run_file` is denied `tool_not_granted` with no connection given, so before any effect |
| No secret in the catalog | PASS | `test_no_key_value_appears_in_the_catalog`: with fake `GITHUB_TOKEN` and `GITHUB_REPOSITORY` values set, no 8-character substring of either appears in the serialized catalog, which names both variables and reads `available`. A blank value reads `key_missing` with `github_key_missing`. The digest is equal with and without the values, so it can't encode them |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (571), lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/qualify_web.py` | 0 | 33 browser tests passed, 0 failed, 0 skipped |
| `openspec validate us-14-1-tool-catalog-api-derived` | 0 | valid |

## Findings

**Found and fixed, not from this change:** the browser test "status meaning is in text and icon, not color alone" failed on the code before this change. The owner's restyle in `ec8b31a` added a decorative CPU icon to the status badge, so the test counted two SVGs. The state icon now carries `data-status-icon` and the test counts that one. Its meaning is unchanged.

**Typing found and fixed:** mypy rejected `grant_sites`' `list[str]` for the contract's literal list, and a tuple widened by `+=`.

**Suggestion, not blocking:** the generated client's `listTools` takes no query filters, because the generator emits path parameters only. The filters were exercised through the API tests.

## Limits

- Availability reads the API process's environment. The worker reads its own, so the two agree only when both start from the same configuration, as the runbook's start does.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
