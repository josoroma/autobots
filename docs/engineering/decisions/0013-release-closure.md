# Decision 0013: What closes the release

**Date:** 2026-11-06. **Authority:** the owner, who went through [US-10.2's open items](../evidence/US-10.2/summary.md#what-stops-a-release-now) and chose one option for each. Each choice below was the option recommended to them.

## Decision

| Item | Choice |
|---|---|
| **H1.3's records** | US-11.12's record carries the baseline. US-1.3 to US-1.7 keep no DH-W record, and H1.3 is [revised](#requirements-revised). A later review and Gate 0 at the final code takes its place |
| **LC-23 on Terra** | Revised. Reasoning metadata is preserved where the pinned SDK passes it on. Terra's encrypted reasoning `id` is removed by that SDK, and stays a stated limit |
| **The real install** | Back it up, apply its pending migrations from a restored copy first, start it, and run one real goal on Terra, at the final code |
| **DeepSeek** | Not offered for new runs until it's qualified. The profile, its records and runs already admitted stay as they are |
| **The two-call workload** | Measured: two goals at once on Terra, on a disposable stack, recording CPU, memory, disk and connections |
| **PRD 12.2's metrics** | Later scope, with the requirement [revised](#requirements-revised) |
| **Review items marked later** | PRD 9.2's approval fields and held-out replay get post-release stories. The rest are accepted as limits for a single-owner release: PRD 8.3's empty `inputs` grant (N-7), `authenticated` reading raw emissions within a workspace (N-37), a rollback's actor and a promoted memory's `created_by` (N-51, N-52), and routines reading policy and skill text at each occurrence (N-48) |
| **A third real sleep** | The owner sleeps this Mac once more on the final code, following [the runbook](../runbooks/mac-sleep.md) |
| **Partial rows a test can settle** | One story closes them, with round 5's small fixes, ahead of a new review and Gate 0. Whatever a test can't settle stays a stated limit |

**Spending:** the goal on the real install and the two-call measurement count against the same US$1 cap as [Decision 0009](0009-release-scope-from-blocking-findings.md), by its ledger, with actual key usage recorded beside it. US$0.008174 of it was used when this was decided. It covers nothing else.

**What this authorizes:** the real install's backup, migrations, start and one goal, and the paid measurement, within that spending. These are the delivery rule's stopping points for the two stories that do them. Everything else still stops there.

## Requirements revised

IDs stay, and each requirement's text is edited to match.

- **H1.3:** for H0 and H1 stories delivered under Decision 0003, the record of the final review and Gate 0 carries the baseline.
- **LC-23:** preserved reasoning metadata is tested where the pinned SDK passes it on, with Terra's removed `id` stated.
- **MP-01, MP-10, SP-006 and PRD 6:** DeepSeek stays approved in the registry, and isn't offered for new runs until a recorded qualification and a decision bring it back. A choice saved earlier that names it is refused with no substitute, as MP-01 allows no fallback, and isn't rewritten.
- **Older text:** finished stories that assume two choices, such as US-11.6 and US-11.9, read under this decision without being rewritten.
- **PRD 12.2:** queue wait, inference wait, time to first token, generation duration and the other measured fields are later scope. Structured logs, Operations and the inspector are what this release has.

## What this gives up

- **Terra may lose reasoning continuity between calls.** Continuations worked in the trials, on a small sample.
- **One route for new work.** A person can't choose a cheaper model, at about one fifth of Terra's price per call, until DeepSeek qualifies.
- **No timing metrics in this release** beyond what US-10.1 measured with its runner.
- **Accepted audit gaps.** A rollback and a promoted memory don't say who did them.

## Reversal

Each can be changed later under its existing ID. No data depends on these choices. Bringing DeepSeek back needs a recorded qualification and a decision.
