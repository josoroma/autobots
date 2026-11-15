# REFACTOR-R21-R40: refactor-plan items R-21 to R-40

**Date:** 2026-11-14. **Status:** done on branch `refactor/r21-r40` at `87a0798`, not merged or pushed. **Scope:** the owner asked to work "from R-21 to R-40" of [the code-quality review's refactor plan](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md) and to make the decisions that would otherwise wait for them. Those decisions are [Decision 0028](../../decisions/0028-refactor-decisions-delegated-r21-r40.md). R-01 to R-20 are recorded in [REFACTOR-R01-R20](../REFACTOR-R01-R20/summary.md). This short record follows DH-W01–06, outside the OhMyOrch delivery loop. The review is static analysis, not acceptance evidence.

## Plan

Each item's steps, files, risk and verification are in the plan's own section. The twenty items overlap heavily in files, so they were delivered in rounds of up to three, each implemented by a specialist that owned disjoint files: the service's core items one at a time (R-21, R-22, R-24, R-25, R-29, R-30, R-31, R-33, R-34, R-35, R-36), the web items in their own lane (R-26, R-27, R-28, R-37, R-40), and the scripts and database-check items in a third (R-38, R-39, R-23, R-32). Tests came first wherever the plan asked for them. Each round passed `fast` before its items were committed, one commit per item.

## Implementation

| Item | Commits | What now holds |
|---|---|---|
| [R-21](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-21) | `a786fc3`, `16ef27f` | `approvals.return_to_review` holds the lease, settles the receipt, returns the request to pending with `DEFAULT_TTL_SECONDS` and appends `approval.requested` in one fenced transaction. A stale generation writes nothing, and an attempt whose lease was lost doesn't use the person's decision. The run enters the wait when the call is retried (E1). |
| [R-22](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-22) | `0f9789f` | Paid trials price calls with the application's catalog parser, refuse an unbounded price before reserving, and settle every exit path, cancellation included, through one `Ledger.charge`. |
| [R-23](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-23) | `8aa598d`, `d83371a` | `scripts/paid_run.py` is the one paid-run session for the four paid entry points, with its decisions tested on fakes. Unreadable spend fails closed (E2), every entry point's wiring is tested, and an unknown spend counts at the whole limit. A variable an earlier rename left unbound in `qualify_release` is fixed. |
| [R-24](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-24) | `af402d7` | One readiness gate refuses a due routine for the same conditions as a person's run, `schema_behind` included, and its settings are read once at start. |
| [R-25](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-25) | `b75e164`, `30eecf8` | Logs carry an exception's qualified type, causes and frames, never its message; unknown receipts record why; a 500 logs its route; a database error is a retryable 503 only when a retry can succeed; `stop_task` keeps the caller's cancellation. |
| [R-26](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-26) | `9184708`, `16ef27f` | Server reads are ok, signed out or unavailable, and only signed out shows Sign in. The BFF logs each failure's cause without values, maps its own timeout to 504, tells an Auth outage from a wrong password, and fails fast on missing configuration. |
| [R-27](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-27) | `ff654ab` | One read hook classifies every read (signed out, denied, not found, unavailable, out of date), and six screens use it. |
| [R-28](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-28) | `1b5e627`, `30eecf8` | The run page stops polling on a refusal, backs off on an outage with a visible Retry, and never lets an older snapshot replace a newer one. |
| [R-29](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-29) | `f94a08e` | `domain/stops.py` maps every stop code to its disposition, tested exhaustively. An unmapped code pauses the run (E3), and a pause inside an assignment no longer fails a workflow run for good. |
| [R-30](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-30) | `62ee377`, `87a0798` | Admission takes a typed `RunAdmission` with a `Fresh` or `Inherited` origin. Golden fingerprints captured before the change still match byte for byte, through the real call sites too. |
| [R-31](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-31) | `4715a17`, `6cb0a91` | One admission use case and one gate for model-backed work, used by every handler, each stating its deliberate differences. A workflow's preview shows the model its child run will use (E6). |
| [R-32](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-32) | `348ec1f` | The paid-path tests use seams whose defaults are today's guard and admission, and one fake-provider kit covers the three profiles. |
| [R-33](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-33) | `2f61123`, `87a0798` | `application/run_lifecycle.py` holds the run lifecycle and the lease keeper, `workflow_runner` no longer imports `goal_loop`, and the db checks drive public seams (E7). |
| [R-34](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-34) | `d25bfea` | A pass's ending is decided by a pure `decide(code, observed)` over one read. A refused command reports `command_refused`, and a person's pause mid-pass releases the job. |
| [R-35](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-35) | `176090d`, `87a0798` | Migration 55 records a failed pass privately, and the third consecutive failure pauses the run with `worker_failed` (E4). |
| [R-36](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-36) | `04ab0ed` | A pure `resolve` resolves each tool call once into a `Call`, the approval rule is one `ApprovalPolicy`, and a tool output that fails its model no longer escapes the gateway. |
| [R-37](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-37) | `178e580`, `30eecf8` | Shared run vocabulary, labels and formatting for the web: money never rounds down, and a deadline never reads longer than it is (E5). |
| [R-38](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-38) | `83cb94c` | `tests/db/checklib.py` is the database checks' shared case protocol, and the 32 `sys.path` inserts are gone. |
| [R-39](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-39) | `01b2877`, `16ef27f` | One child-check runner for every qualifier, with typed records. A child that misbehaves records one failed case and never raises. |
| [R-40](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-40) | `9785411`, `30eecf8` | A shared support layer for the browser tests. All 41 specs use it, with the same 231 test names. |

R-37's visible strings that changed: amounts show exact sub-cent values ("US$0.001234", not "US$0.00") and two decimals ("US$0.50", not "US$0.5"); "Failed · budget" reads "Failed · budget exhausted"; approval expiries read "in 4 minutes", "in less than a minute" or "in 1 day" rather than "in 5 min" or "tomorrow"; Experts cards read "last run 5 minutes ago"; workflow durations read "2h 00m" rather than "120m 00s"; the run panel's start time is a UTC timestamp; and the workflow monitor says "Run: Failed".

## Review

Independent read-only reviewers (`autobots-reviewer`) inspected every item, in four rounds, and ran nothing.

- **R-21, R-22, R-38, R-39: approve, five should-fix**; **R-26, R-27: changes needed, nothing blocking, five should-fix.** Answered in `16ef27f`: a lost lease no longer consumes an approval, qualifier timeouts and empty reports can't pass or raise, the CSRF cookie follows the origin, a configuration failure names its variables, a gateway 401 isn't a wrong password, and Sign out stays offered while the API is down.
- **R-24, R-25, R-29, R-32: approve, four should-fix**; **R-23: approve, three should-fix**; **R-28, R-37, R-40: approve, three should-fix.** Answered in `30eecf8` and `d83371a`: a tool can't claim a gateway-only receipt code, the catalog and search read the start-up environment, a database 503 is limited to errors a retry can clear, the approval countdown ticks, and every paid entry point's wiring is tested.
- **R-30, R-31: approve, two low should-fix**; **R-33 to R-36: approve, two should-fix.** Answered in `87a0798`: the golden fingerprints are pinned at the real call sites, a cancelling run's settlement at the bound runs on a live lease and is released if it fails, and the workflow driver is required.

Specialists also stopped three times on a decision their scope couldn't make, and each became a recorded decision: E1's immediate wait, which wasn't safe yet; E6's preview mismatch; and E7's placement of shared run types.

## Verification

All at `87a0798`, with no edit during any run.

| Check | Exit | Observed |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed: harness 436 tests, service pytest (1515 collected), API client 48, web unit 199, ruff, mypy, repository ruff and mypy, ESLint, Prettier, typegen, typecheck, contract drift, non-mutation guard |
| `python3.12 scripts/verify.py --profile db` | 0 | Passed: app_db 615 of 615 and identity 724 of 724, including the stale-lease and moved-base approval cases, the readiness gate, the stop-code race, the admission replay, the worker-failure bound and the browser suites R-40 migrated |
| `python3.12 scripts/verify.py --profile full` | 0 | Passed: the production build, fault and toolchain-scope checks (20), and the web qualification at 50 of 50, including the boundary and tools browser specs |
| `python3.12 scripts/verify.py --profile operations` | 0 | Passed: operations 73, backup 51 and upgrade 50 cases on new disposable Compose projects with a scripted model; the upgrade applies migration 55 to an older install |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed, after this record |

Earlier `db` runs caught defects that were fixed before this one: two spec expectations from R-37 and R-40, database checks that still called the gateway's pre-R-36 signatures, a check that simulated a worker's death with an exception R-35 now records, and the preview expectation E6 changed.

## Runbook

No operating procedure changed. A persistent install receives migration 55 (and 54, if it hasn't yet) only through the guarded apply (`make migrate`), then needs the web app rebuilt and the service restarted. The API and the worker now refuse to start on a malformed `AUTOBOTS_MIN_FREE_BYTES`, naming the variable and never its value.

## Limits

- Static, mock and disposable evidence only. Nothing was checked on the persistent install, no paid call was made, and none of this establishes H1 or product acceptance.
- Open decisions left to the owner: whether a moved base should enter the decision wait at once, which needs a "returned to review" stop first (E1); and whether a workflow agent step's child should follow its Expert's model bindings ([PPRD-09](../../../reviews/review-2026-11-12-09-52-30/findings/py-product.md#pprd-09)), which would change which model a paid step uses (E6).
- A run whose cancellation settlement keeps failing stays cancelling, retried every 60 s and logged, since SP-010 forbids finishing a cancel unclassified (E4). A parent sees a paused or refused child as lost; both pause the parent.
- Not yet moved: the fake-provider kit into the database checks (R-32), most database checks onto `checklib` (R-38, by design when next touched), routines' tool keys onto the start-up environment (R-24), and profile names onto the models endpoint (R-37, which needs a contract change). Some re-exports from `goal_loop` remain for callers outside R-33's scope.
- Smaller follow-ups the specialists named: the workflow monitor doesn't pause while the tab is hidden; concurrent identical reads are shared by path alone; the charge field still accepts `Number()` forms such as `1e3`; and a narrow race between `finish`'s read and its row lock behaves as before.
- One disposable Docker project from before this work (`autobots-disposable-cb16aed9`) is still running and was left for the owner.
