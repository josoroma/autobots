# Verification — us-1-6-h1-deliberate-fault-freshness

Change: us-1-6-h1-deliberate-fault-freshness
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `239fb37`, working tree with this change. No real model call, service or database. The "real provider key" is arranged: a placeholder, `arranged-not-a-real-key`. No real credential was read or used.

## Scenarios

**Detect faults and invalidate old evidence: observed.**
- `scripts/qualify_faults.py` on the real tree with the pinned tools: 21 of 21 cases behaved as expected, exit 0. Bad cases detected: `F401` (ruff), `return-value` (mypy), a failing pytest, `TS2322` (tsc), `no-explicit-any` (eslint), contract drift, a resumed terminal run, a skipped verification, a wrong reducer, a private key in a public event, a real transport and an unapproved model.
- The first run correctly refused a bad fixture: `model_real_bad` failed on a missing key instead of the socket block, so it was not counted until the fixture was fixed. `--types ""` was a separate invocation error in the case table, also fixed.
- Arranged in a disposable copy with its own Git history and bootstrapped environments, deleted afterwards. A real Python type fault: `fast` exit 1 on `mypy`, corrected exit 0. A real TypeScript fault: `fast` exit 1 on `typecheck`, corrected exit 0. A bad contract fixture repaired: qualification exit 1, "its fault went undetected".
- Staleness in that copy: after a clean `full`, `report_state` was true. An untracked `services/agent/src/autobots/untracked_input.py` made it false, "inputs changed after the last full check". It was true again once removed.
- Manifest validation against that copy's real fingerprints: 0 problems when current. A changed lock, config, verifier and source file were each named as stale. A template, a missing reviewer, an unexercised runbook, `passed` with exit 1, an open blocking finding and a fake model as `live` were each rejected.
- Real `full` on this tree: exit 0, including `fault_qualification`, inputs stable.

**Protect paid endpoints during tests: observed, with the key arranged.**
- `OPENROUTER_API_KEY=arranged-not-a-real-key .venv/bin/pytest`: 27 passed. `test_no_inherited_provider_key_reaches_a_test` shows the conftest removed it.
- `test_each_approved_profile_round_trips_through_the_fake` runs both wire IDs through the real `ChatOpenRouter` and `openrouter` SDK over `httpx.MockTransport`. An unapproved model, a fallback array and a missing key are refused.
- `test_external_inference_is_refused_even_with_a_key` and the bad fixture use the real transport with the arranged key: `SocketBlockedError` in the exception chain. A guard failure could not have spent money, since the key is not real.

## Findings

- **Not the product's behavior.** The state and contract checkers and the fake transport are fixtures. They do not qualify the state machine, contract generation or gateway. Real routes stay with US-3.4.
- **The socket block is a guard on Python tests.** It covers `socket.socket.connect`, `connect_ex`, `sendto`, `create_connection` and `getaddrinfo` in `services/agent` pytest, so a native extension or subprocess could bypass it. It is not OS confinement.
- **Only `OPENROUTER_API_KEY` is removed by name.** `verify.py` children also get a reduced environment, but a direct pytest run keeps any other variable.
- **`tests/toolchain/test_scaffold_scope.py`** now allows the two new test files. Later stories adding product code must extend that list on purpose, or it fails; only its direct run was exercised here.
- **Order:** the fixtures were written before this change's artifacts, inside the same `implement` work. The artifacts describe what was built and were not a prior plan.
- **DH-A coverage here:** A02, A04, A05, A08, A11, A14 and A15 have this evidence at fixture level. A03's Claude behavior and A13's sample work item are not covered; US-1.8 owns the closure.
- **Runbook:** the added section's commands were run as written.
- This is not H0, H1 or product acceptance.
