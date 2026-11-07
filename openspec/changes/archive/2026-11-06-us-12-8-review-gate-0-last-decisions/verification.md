# Verification — us-12-8-review-gate-0-last-decisions

Change: us-12-8-review-gate-0-last-decisions
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Review what changed and repeat Gate 0 | PASS | Three fresh read-only rounds, in `docs/engineering/evidence/US-12.8/`, ending approved on source fingerprint `51212ae1…`. `harness`, `fast`, `full`, `db` and `operations` exit 0 under `env -i`, and `qualify_worker_inference.py` passes 55 of 55, by hand. `scripts/evidence.py validate US-12.8` passes, and the record leaves H1 and product acceptance to US-10.2 |
| Read the correction left unread | PASS | Round 1 read the corrected release record and found 4 blocking items in it, recorded with the others |
| Say plainly what ran earlier | PASS | The summary's table says US-12.4, US-12.5 and US-12.6 ran at `05916d5e…` or older, lists the inputs that differ by `git diff 70c5162`, names the captures as not repeated, and says no paid call or persistent change was made |
| Carry the H1.3 baseline | PASS | The summary's opening says so, and doesn't claim H1 |
| Void a stale binding | PASS | A fix in round 1 and round 2 moved the fingerprint each time, and the checks ran again. Gate 0 ran only after round 3 approved, and the manifest's fingerprint equals the one round 3 read, by the coordinator's comparison |
| Mark the hook behavior not qualified | PASS | The summary's mark on the hooks, DH-A03 partial, and the adapter's `configured_unqualified` |
| Keep earlier records as history | PASS | US-12.3's summary says it's replaced, as US-11.12's does. Neither was otherwise changed, so `validate US-12.3` no longer passes on the current tree, as its binding says it shouldn't |

## Findings

- **My check couldn't fail.** RG-1: "nothing stayed reserved" came from a column nothing writes. Reading the ledger showed 34,560 micro-USD held on all 12 cancelled runs.
- **Reviewers read code and don't run it,** so "this check fails without that guard" is by reading. No mutation was run.

## Not exercised

Nothing live, no real sleep, and not the real install, at this fingerprint. Decision 0014 authorizes none of them.
