# Verification — us-14-5-tool-provider-key-readiness

Change: us-14-5-tool-provider-key-readiness
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 6/6 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed: two on a disposable stack with real Auth, one with sockets blocked |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| A missing key disables only its provider's tools | PASS | `apps/web/tests/browser/experts.spec.ts` "US-14.5", run by `scripts/qualify_identity.py` in the `db` profile. `tests/db/provider_key_check.py` saves two Experts while the GitHub variables are set, one granting `create_github_issue` and one only `calculate`, with a session each; the suite's API has no GitHub variables. Through the BFF, a run on the connector Expert's session is refused 409 `tool_unavailable` and the run list doesn't grow, while a run on the plain Expert's session is accepted 202. A new version still naming the connector is refused 422 `expert_tool_unavailable`, and one without it saves 201. The catalog's only `key_missing` tool is `create_github_issue`, and it carries no token shape. Routine occurrences take the same refusal through `require_available`, by code; no routine case ran |
| A key stays out of durable state | PASS | `tests/db/provider_key_check.py`: a fixture provider tool built on `provider_key` and `provider_client` runs through a real Deep Agents loop with the gateway middleware, an in-memory checkpointer and a scripted model, against a fake transport that received `Bearer <fake key>` once. The fake key was found in no table of `public`, `app_private` or `agent_runtime`, nor in the graph state, the messages the model was shown, the checkpoints (their repr and their pickled form), the scope, the tool schema the model saw, the catalog, or captured log lines. The tool's input has only `query`. With the key unset, the call fails `fixture_key_missing` and the transport receives nothing more. Unit tests show log redaction removing Tavily, Jina and GitHub key shapes, and the evidence validator rejecting them |
| No automatic live key check | PASS | `services/agent/tests/test_tool_catalog.py`, where `conftest.py` blocks every socket: with a real-looking GitHub token set, the catalog reads `available` and no connection is attempted; a provider client sends only through the fake transport it was given, with redirects off. No test in either profile has a provider transport other than a fake |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `identity_qualification` with the provider key cases and browser test, `harness_behavior_tests` with the evidence test, `app_db_qualification`, `non_mutation_guard` and the rest passed |
| `openspec validate us-14-5-tool-provider-key-readiness` | 0 | valid |

## Findings

**Found and fixed:** the first run of the key check stopped because the scripted model lacked `bind_tools`; it now records the messages it is shown, so prompts are scanned too.

## Limits

- The API and the worker each read their own environment, so availability on the Tools page is right only when both start from the same configuration, as the runbook says.
- Tavily's and Jina's key shapes (`tvly-`, `jina_`) are as their providers show them, not confirmed against a live key. A different shape would still be unscanned in logs and evidence, though never stored by the code.
- **Not established:** that any provider accepts its key. H1 or product acceptance. No independent review ran, under Decision 0003.
