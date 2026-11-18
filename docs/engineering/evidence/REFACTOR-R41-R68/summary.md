# REFACTOR-R41-R68: refactor-plan items R-41 to R-68

**Date:** 2026-11-17. **Status:** done on branch `refactor/r41-r68` at `b6e2e6f`, not merged or pushed. `db` and `operations` have not run on the final review-fix commits (see Verification). **Scope:** the owner asked to work "from R-41 to R-68" of [the code-quality review's refactor plan](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md) and to make the decisions that would otherwise wait for them. Those decisions are [Decision 0029](../../decisions/0029-refactor-decisions-delegated-r41-r68.md) F1 to F13. R-01 to R-40 are recorded in [REFACTOR-R01-R20](../REFACTOR-R01-R20/summary.md) and [REFACTOR-R21-R40](../REFACTOR-R21-R40/summary.md). This short record follows DH-W01–06, outside the OhMyOrch delivery loop. The reviews are static analysis, not acceptance evidence.

## Plan

Each item's steps, files, risk and verification are in the plan's own section. The 28 items overlap heavily, so they went in eleven rounds of two to five specialists with disjoint files, each specialist reading and planning while the previous round's profiles ran, then implementing once the tree was free. Service items that touch most modules (R-50, R-54, R-63) and the test refiling (R-66) ran alone. Every round passed `fast`, `db`, `operations` and `full` before its items were committed, one commit per item, apart from the final review fixes (see Verification); where items shared a file, the file went to the later item's commit, which its message says.

## Implementation

| Item | Commits | What now holds |
|---|---|---|
| [R-41](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-41) | `017c10c` | Every refusal derives from one `Refusal` base with a kind, and one handler in `api/errors.py` maps each kind to its status, code and wording, pinned by 194 response cases. The ledger raises typed exceptions where it compared strings. |
| [R-42](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-42) | `59663ee` | `goal_loop` keeps the pass and its graph; prompts are `loop_prompts.py`, a candidate's verdict `settlement.py`, and job dispatch `operations/job_dispatch.py`, which the worker imports (F7). |
| [R-43](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-43) | `34accef` | The workflow editor is a folder of parts and hooks, and its one copy of WF-06's label rule is held to the domain's by shared fixtures (F1). |
| [R-44](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-44) | `266df41` | The goal composer is a folder, with attachment rules and budget choices in tested `lib/` modules. |
| [R-45](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-45) | `d50c162`, `b3342db` | The approvals panel is a folder, with its wording and field rules in tested `lib/` modules; a failed read says why, and a decision that settles under Decided reloads Decided. |
| [R-46](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-46) | `daab18e` | The slice visual walk is typed probes, data and named steps, covering every route in both themes. |
| [R-47](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-47) | `a110f34` | `qualify_identity`'s arrangements are registered functions with their SQL in files, in a pinned order. |
| [R-48](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-48) | `a52c84e` | The generated client types query and header parameters, `Idempotency-Key` is a required argument, and the browser calls the API only through it; raw `fetch(` is down to four transport files. |
| [R-49](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-49) | `665c11d` | RunWorkspaceView is a 52-line composition, the run views are folders with pure rules in `lib/runs/`, and `RunWorkspace.allowed_commands` comes from `next_status`, so the browser no longer re-derives SP-010. |
| [R-50](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-50) | `e820bb1` | `domain/effects.py` holds the receipt and approval machines, `receipts.py` and `approvals.py` are their only writers with guarded moves, adapters send no SQL to those tables, and migration 56's `consumed_at` makes an approval that releases a receipt-less call single-use (F8). |
| [R-51](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-51) | `1ef8330` | The policy snapshot, stored event payloads and receipts are typed persisted models with legacy shapes read explicitly and bytes pinned to HEAD's writers. |
| [R-52](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-52) | `d2210c7` | Stored Expert and routine configurations, goals and plan tasks read through lenient versioned records; the routine trigger is the cronjob schedule, and a person's routine keeps the workspace limit while the model's is capped (F2, F9). |
| [R-53](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-53) | `b95d5e7` | The tool registry is built once at the composition edge and passed in; one resolver applies key precedence for every item, and adapters can't reach `ToolContext.connection`. |
| [R-54](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-54) | `cf837f8` | A psycopg-free SQL boundary: `one()`, typed rows bound by column name, enums for stored statuses, one `AppResources`, and run views that each read from one snapshot; the approval contract also accepts migration 53's `action_marked`. |
| [R-55](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-55) | `e509d1b` | Route handlers hold no SQL, share `api/dependencies.py`, decode the token once, hold one pool connection at a time, and cap LISTEN connections at ten. |
| [R-56](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-56) | `daccc6f` | Migrations 57–62 add run-lookup indexes, `run_is_terminal`, the draft shape CHECK and four version foreign keys (validated by 61), and Sol's concurrent-admission caveat; superuser files have checksummed bootstrap history, and members no longer write Storage (F3). |
| [R-57](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-57) | `5f1ae43` | The browser images are built by `make browser-images` and labelled with their source fingerprint, and the qualifier refuses others; the executor is split into three modules (F4). |
| [R-58](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-58) | `fe68ce7` | Seven Playwright projects select the specs, shared states are checked and restored by fixtures, and `waitForTimeout` is banned with today's commented sleeps as a baseline. |
| [R-59](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-59) | `72ab59d` | The remaining large screens are folders split into data hooks, action hooks and sections, with shared list scaffolding and one filter. |
| [R-60](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-60) | `17207e4` | Run and job writes go through one transitions surface with an actor table that includes `system` (F5), every path locks job, run, then request, and spend is admission's one fragment (F10). |
| [R-61](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-61) | `dadc5e5` | Strict request primitives, response vocabularies held to the domain and the SQL CHECKs, UTC timestamps, published stop codes, and byte-identical tool schemas (F13). |
| [R-62](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-62) | `ceb1615` | One client factory with no redirects or proxy variables, lenient reply models, one refused-status table per write class, connectors with module handlers, and the loop's policy in the application; the URL guard requests the address it checked. |
| [R-63](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-63) | `63f1b99` | The workflow domain's pure rules, block tables pinned to `BLOCKS`, `receipted` and `next_version`, one occurrence admission, batched list reads, and the product tools out of the services (F12). |
| [R-64](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-64) | `7bee890` | `autobots/logs.py` is a leaf, process wiring is `operations/composition.py`, entry points share exit codes 0/1/2, and owner bootstrap prints a recovery for every outcome; DH-03 follows the code (F6). |
| [R-65](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-65) | `82c49de` | One profile registry, one disposable-stack lifecycle, ordered qualifier scenarios, the Makefile's supervision in `scripts/local_app.py`, and one dotenv reader (F11). |
| [R-66](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-66) | `6256a7b`, `311ab06` | `tests/db` is grouped by role with a README of invokers, the largest checks run ordered scenarios with unchanged case IDs, and service and harness tests are filed by subject. |
| [R-67](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-67) | `d9bb3a2` | Read-only views render on the server with per-request caching, writes refresh server data, and list filters live in the URL. |
| [R-68](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-68) | `fa4efbd` | Label, Field and Dialog primitives, shared layout pieces, a named type scale with a falling pixel baseline, and one preferences module. |

Visible changes the owner may notice:

- **Web:** the large screens use the shared load-state wording with Retry where nothing read the old sentences, "1 hour ago.", and only the card being saved says Saving (R-59). Read-only pages render on the server, list filters and selection live in the URL, and a write refreshes server data (R-67). Search, About and the tool guide close on a click outside them that began outside, Settings pages have titles, and the search field keeps its control border (R-68, Decision 0023 E1). Approve and Reject are disabled while a decision is in flight, and the composer says when the Experts or models read failed.
- **API:** a malformed routine trigger is `422 invalid_request` (F9); response timestamps end in `Z`; a bodiless draft discard sends no `Content-Type`; search encodes spaces as `+`; GitHub read failures map to one table, and a 422 on a pull-request create settles by readback (R-62); a configuration error at start-up exits 2 with `ERROR:` (R-64); an approval held by `action_marked` reads instead of failing.
- **Database:** migrations 56 to 62 and one bootstrap file (members no longer write Storage).

## Review

Independent read-only reviewers (`autobots-reviewer`) inspected every item and ran nothing. Every finding marked blocking or should-fix was fixed before the item's commit or in the final review-fix commits (`6e5daff`, `6299aef`, `70bacd9`). Fixes before those passed all four profiles again; the final ones passed `full` and await `db` and `operations`.

- **Blocking findings, all fixed:** R-52 (Experts read through the request type, so a stored Expert with more than twenty tools failed the list), R-54 (the upstream fixture read a removed `app.state` attribute, so real catalog calls could have left a test; and `pull_request_check` indexed the new approval rows), R-56 (the backup qualifier counted bootstrap rows as migrations).
- **Should-fix findings fixed, among others:** a lost lease could still consume an approval (R-50); two scheduling paths could start paid catch-up runs or schedule a non-text time (R-52); duplicated Runs lists from a theme provider wrapping streamed sections (R-67, found in `db` and reproduced on a disposable stack); deadlocks between an expiry, a decision and a cancel (R-60); a request holding two pool connections (R-55); an IPv6-first host failing the URL guard, and a lost readback read as a defect (R-62); writes that skipped `router.refresh()`, lost filter clicks and pages awaited outside Suspense (R-67); a dialog closed by a drag (R-68); the image check blocking the event loop and lease queries outside the fingerprint (R-57); scenarios that kept running after a failure (R-66).
- **Rounds 1 and 2 (R-41 to R-47, R-57)** were reviewed after the rest, because the review step was still pending when this work was first summarized. The scratchpad holding their diffs was cleared mid-review, so R-42, R-44, R-45, R-46 and R-47 were reviewed against the current tree rather than as landed; R-41, R-43 and R-57 were reviewed from their diffs.

## Verification

At `b6e2e6f`, after the final review-fix commits, with no edit during any run.

| Check | Exit | Observed |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed before the last web fix (the server-read marker); `full` repeats every `fast` check after it |
| `python3.12 scripts/verify.py --profile full` | 0 | Passed: every `fast` check (harness 603, service pytest 2971, web unit 451, API client, ruff, mypy, ESLint, Prettier, typecheck, contract drift), the production build, fault and toolchain-scope checks, and the web qualification at 57 of 57, including the server-read states. The first run failed three server-read cases where the composer's new load states sat beside the page's own; the page's read is now marked and the spec reads it |
| `python3.12 scripts/verify.py --profile db` | 2 | Unavailable: the Docker engine was not reachable, so no disposable stack could start. Not run on the final review-fix commits |
| `python3.12 scripts/verify.py --profile operations` | not run | Needs Docker, as `db` does |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed, after this record |

Before the final review-fix commits, the tree at `311ab06` passed all four profiles: `db` with identity 739 of 739 and app_db 667 of 667, `operations` with 73, 51 and 51, and `full` with web 57 of 57. R-66's moves were compared with the tree before it (`63f1b99`) by collected test IDs and by every case-ID expression: nothing was lost; the differences are moves, one parametrized test split into two, six new harness tests, and the embedding scan moving from app_db to the harness.

## Runbook

The persistent install is at migration 55 and needs, in order, after a backup taken as [the backup and restore runbook](../../runbooks/backup-restore.md) describes:

1. Before `make migrate`, run migration 61's header queries against the install as its header says; 61 validates the new constraints and stops on rows that would fail them (`docs/engineering/runbooks/local-supabase.md`).
2. `make migrate`, which applies migrations 56 to 62 and then the bootstrap file through the guarded apply.
3. `make build` and a restart (`make start`). The API and worker now exit 2 on a missing or malformed setting.
4. Optionally, to turn browsing back on: `make browser-images && python3.12 scripts/qualify_browser_executor.py` (F4). Until then `browse_goal` stays off, which is the safe state.

## Limits

- Static, mock and disposable evidence only. Nothing was checked on the persistent install, no paid call was made, and none of this establishes H1 or product acceptance.
- Owner questions left open on purpose (F11): whether `stack.env`'s quoted `MAILER_URLPATHS_*` values are right, and resource limits for the install overlay.
- Deferred by decision (F12, F13): the profile foreign key until the approved set changes, the egress proxy's own address choice until re-qualification, tool-schema constraints that would version eight tools, and one `RefusalCode` enum.
- Left undone, as each item's specialist reported: `FakeDatabase` stays permissive; the `tests/db` mains beyond the eight largest keep their linear form; some `asyncio.run` calls remain in sync helpers; a worker pass still reads the frozen snapshot up to four times; the browser preflight scripts and several manual qualifiers ran only offline; the egress proxy keeps its sorted-address choice. The server-rendered failure states are proved in `full`'s web project rather than in `db`.
- The R-59 commit's message says nineteen lint suppressions were removed; it was 22 counts across nine files.
