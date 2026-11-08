# Verification — us-15-18-operations-verdict-check-detail

Change: us-15-18-operations-verdict-check-detail
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 4/4 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0. Pytest ran 809 tests, including the 6 in `test_operation_values.py`. Contract drift, lint, types and web unit tests passed.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T16:15Z. Every check passed, including `app_db_qualification` and `identity_qualification`.
- **`python3.12 scripts/verify.py --profile full`:** exit 0. The production build and its browser suite passed.

## Scenario: Verdict — PASS (browser, disposable stack)

The `ops-n` workspace has one job that lost its worker, plus one leased and one queued job that no worker may take. `tests/db/operations_live.py` started two live heartbeats, which `afterAll` stops again. On Operations:
- the page says "Ready. New work can start.";
- 8 checks show, 7 with state ok; the queue is degraded, with "A job lost its worker.";
- the verdict reads "7 of 8 checks pass", "2 workers" and "no hold", the first counted against the cards shown;
- axe found no violations at WCAG 2.2 AA.

## Scenario: Values beside checks — PASS (browser, disposable stack)

The spec first made 20 readiness probes through `/api/v1/readiness`, each answering 200. Each value then showed beside its check:
- **Database:** `p95 N ms over the last 20 probes.`
- **Schema:** `49 migrations applied.`, matching the 49 migration files counted by the spec.
- **Storage:** `3,345 bytes in published artifacts.`, the two published artifacts; the staged 999-byte one isn't counted.
- **Disk:** `X GB free of Y GB.`
- **Queue:** `1 leased, 1 queued.`
- **Checkpoints:** `LangGraph checkpoint adapter <release>.`
- **Worker:** `2 workers.`
- **OpenRouter:** "The catalog answered in N ms."
- **Network:** "the API listens on this Mac's loopback only." The fixture API is served by uvicorn on 127.0.0.1.

Offline, `test_operation_values.py` checks:
- the p95 is the nearest rank over the newest 20 probes;
- a probe that finds no database records nothing;
- the bind check returns null with no listener, true for a loopback listener (IPv4 and IPv6, checked by hand) and false once a wildcard listener exists;
- the catalog time is measured only when the catalog answers.

## Scenario: Numbers only, and nothing more — PASS (unit, and browser on a disposable stack)

- **Fields:** `OperationValues` has exactly the 12 fields D5's list maps to, and the browser read the same 12 keys from the live response.
- **No paths or secrets:** the browser found no `/`, `\`, address or token shape in the values, and no `/Users/`, `/private/`, connection URL, `sk-or-` or `eyJ` in the whole body. Remote tracing reads `disabled`.
- **Nothing sent:** the unit test produced the status through the real route with every outbound connect guarded, and recorded zero non-loopback connections. Its body held no `/`, `\`, address, connection URL, token or secret.
- **Upstream:** the identity qualification's own case confirmed that only `GET /api/v1/key` and `GET /api/v1/models` reached the fake upstream.
- **Grants:** the runtime role reads the count (49) but not the migration history, and `authenticated` can't call the function.

## Scenario: Existing sections stay — PASS (browser, disposable stack)

As owner A, with a backup manifest from 3 hours ago and a restore record arranged in the backup directory, Operations shows:
- the delayed schedule "Arranged nightly report";
- "Last backup: 3 hours ago.";
- the restore "verified, 12 of 12 checks";
- "Remote tracing: off";
- the model routes;
- the Retention heading;
- the verdict line.

The existing Operations specs still pass unchanged, including the one that finds no address, "postgres", key or token in the page.

## Findings

- **Interpretation (design.md):** the catalog fetch time is the duration of this page load's existing catalog check, since the catalog isn't cached. Storage bytes are the workspace's published artifact sizes, not Storage's own accounting. The probe window lives in the API process and starts empty after a restart.
- **SUGGESTION:** the bind check reads this process's descriptors. A bound TCP socket with no peer counts as a listener, since macOS doesn't answer `SO_ACCEPTCONN`.
- **Not established:** H1, product acceptance, or behavior on a persistent install. No model was called.
