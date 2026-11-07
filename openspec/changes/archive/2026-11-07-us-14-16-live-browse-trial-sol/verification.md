# Verification — us-14-16-live-browse-trial-sol

Change: us-14-16-live-browse-trial-sol
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 4/4 tasks, 2 reqs |
| Correctness | 2/2 scenarios observed, live |
| Coherence | Followed the proposal. The approval was decided by the trial, for the owner who authorized this one call (Decision 0019 S6). No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| One live read-only browse within US$1 | PASS | `python3.12 scripts/browse_trial.py --key-file .env`, once, on 2026-11-07, on a disposable stack. Evidence class `live`.<ul><li>**Key:** the trial's own process read `OPENROUTER_API_KEY` from the key file. The wrapper never opened it, and the record holds no key.</li><li>**Run:** an Expert granting `browse_goal`, admitted with no model choice. `researcher` froze on `openrouter_sol` (`openai/gpt-6.1-sol`) with a 1,000,000 µUSD limit.</li><li>**Call:** waited for approval, was approved, then ran from `https://example.com/` with `allowed_domains` `example.com` and `iana.org`.</li><li>**Result:** `succeeded`, `stopped: done`, `source: third_party` with its notice. Visited `https://example.com/` then `https://www.iana.org/help/example-domains`, in 2 steps and 2 model calls. The summary says example.com is reserved for documentation examples and is maintained by IANA.</li><li>**Model calls:** both invocations were `researcher` on `openrouter_sol`, `succeeded`, each reserved 85,120 µUSD before sending. The first was charged 1,866 µUSD (663 in, 54 out, `open_link`). The second was charged 3,784 µUSD (1,155 in, 96 out, `finish`).</li><li>**Spend:** 5,650 µUSD charged and 0 µUSD left reserved, within US$1.</li><li>**Tool use:** one metered use, public fields only.</li><li>**Proxy:** connected to `example.com`, `iana.org` and `www.iana.org` only. It refused Chrome's own background requests to `accounts.google.com`, `clients2.google.com`, `update.googleapis.com` and `www.google.com`.</li><li>**Cleanup:** no executor container was left, and other Docker resources were unchanged.</li></ul>Each step's client was the shared `chat_model` over the SDK with `require_parameters` and no fallbacks, on the researcher's prepared attempt from a fresh catalog. `test_each_step_goes_to_sol_through_the_shared_factory_with_tools_required` shows the request's wire ID, required tool choice and routing flags on a fake transport |
| Not repeated without the owner | PASS | Started again without `--owner-requested-repeat`:<ul><li>The wrapper refused before any container started, exit 1. The Docker container count was 34 before and 34 after.</li><li>The trial module, called directly with a nonexistent key file, also refused, exit 1, before reading the key, connecting to a database or calling a model.</li><li>`test_a_recorded_trial_refuses_to_run_again_without_the_owner`.</li></ul>The record is written as `started` before the first paid call, so even a crash counts as the one trial |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/browse_trial.py --key-file .env` | 0 | the live trial above, US$0.00565 |
| `python3.12 scripts/browse_trial.py --key-file .env` (again) | 1 | refused, nothing started |
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest (753) and the rest passed |
| `openspec validate us-14-16-live-browse-trial-sol` | 0 | valid |

## Limits

- **The key came from the key file,** not the workspace's stored credential. Everything else on the call path was the product's.
- `upstream_provider` reads `unknown`: the reply didn't name one.
- **An existing gap, not this change's:** the call's first tool-use row, the one that waited for approval, stays without an outcome. Approval releases the run's lease, so the gateway leaves that row open. The approved attempt is a separate, completed row, and the GitHub connector behaves the same way.
- **One browse of one site.** It shows browsing on Sol working once from start to finish, and nothing about reliability (Decision 0019).
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
