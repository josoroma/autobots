# REFACTOR-R01-R20: refactor-plan items R-01 to R-12 and R-17 to R-20

**Date:** 2026-11-14. **Status:** done on branch `refactor/r01-r20` at `3aa2439`, not merged or pushed. **Scope:** the owner asked to work "from R-01 to R-20" of [the code-quality review's refactor plan](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md) and to make the decisions that would otherwise wait for them. Those decisions are [Decision 0027](../../decisions/0027-refactor-decisions-delegated.md). R-13 to R-16 were delivered earlier ([REVIEW-DEFECTS-001](../REVIEW-DEFECTS-001/summary.md)). This short record follows DH-W01–06, outside the OhMyOrch delivery loop. The review is static analysis, not acceptance evidence.

## Plan

Each item's steps, files, risk and verification are in the plan's own section. They were delivered in the plan's waves: guardrails first (R-01 to R-07), then quick wins (R-08 to R-12), then the hotspot fixes (R-17 to R-20). Tests came first wherever the plan asked for them. Departures from a step are recorded in Decision 0027 D9.

## Implementation

One commit per item, then the commits that answer each review round:

| Item | Commits | What now holds |
|---|---|---|
| [R-01](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-01) | `2795311` | `scripts/suites.py` holds every step's test selection, by glob where the runner allows it. `test_suite_claims.py` fails on a test file that no step runs and that isn't listed as manual with a reason. `test_gate_settings.py` fails when a gate's strictness is weakened. A Node run with no tests, or with a skipped or todo test, fails. |
| [R-04](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-04) | `5a51de9` | `.claude/rules/comments-and-names.md` states the citation, naming, suppression and migration-header conventions. Tests enforce the header and fail on a rule glob that matches no file. |
| [R-02](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-02) | `fedfcd4` | Every operation declares `ErrorResponse` for its refusal statuses. The client throws `HttpFailure` for a non-2xx reply and `ContractError` only for a success that drifts. |
| [R-03](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-03) | `f751434` | The TypeScript runtime enforces every keyword the generator emits, and the generator refuses a keyword the runtime neither enforces nor ignores. Eleven shared boundary cases pass in both languages. |
| [R-05](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-05) | `8901a31` | Ruff ratchets size, complexity, `Any` and broad catches in the service, with dated baselines that only shrink. `test_layers.py` counts the import-direction exceptions exactly. The OpenRouter-only rule is a lint ban. |
| [R-06](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-06) | `060c159` | ESLint ratchets complexity, size, import cycles and type assertions in the web, through a suppressions file that only shrinks. The API client is formatted and type-checked. |
| [R-07](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-07) | `7a24cd8` | `repo_ruff_check` and `repo_mypy` gate the repository's Python in `fast` and `full`; strict mypy covers the hook's trust boundary. |
| Wave 0 review | `4e92b44`, `848fcb3` | The suite claim test follows only the qualifiers a profile runs, the gate configurations are report inputs, the post-edit hint names every profile an edit needs, and the operations leak check sets aside only the exact checkpoint adapter value (D10). |
| [R-08](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-08) | `51aed06` | The database checks evaluate a state-changing call once and judge that value, and catch only the named refusal. |
| [R-10](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-10) | `97feb9c`, `d0b2052`, `b1832e0` | The harness's schema guards read every migration and seed. The run-column grant guard reads each privilege, and catches schema-wide, default (including multi-schema), mixed, unqualified, quoted, PUBLIC and grant-option forms, each with a known-bad fixture. |
| [R-09](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-09) | `2ae8b9b` | Write replies, refusals and stream frames are read through the generated parsers, not casts. |
| [R-11](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-11) | `a6ba5f9`, `d0b2052` | Run-status sets derive from `RunStatus`, including those the service's SQL receives as parameters. The cronjob tool dispatches with `match` and `assert_never`. Dead helpers are gone. |
| [R-12](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-12) | `8a3b8f1` | Stale comments, docstrings and the front-door docs state what holds. |
| [R-20](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-20) | `96188e2`, `d0b2052`, `b1832e0`, `3aa2439` | `search_files` runs in an isolated child interpreter (`python -I -B`) given only its module, with JSON over pipes the event loop writes. It is killed and reaped on timeout and on cancellation, and limits its own CPU time, a soft limit under a hard one, so SIGXCPU stops a runaway match even if the worker dies first (D9). |
| [R-17](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-17) | `d3b34f6`, `d0b2052` | Migration 54 revokes the runtime role's DELETE on runs, run events, workspaces, members and profiles. The db qualification checks from the catalog that the runtime role can delete only workflow drafts in the app's schemas, that every public table enables row level security, that `anon` holds nothing, and that `authenticated` holds nothing outside `public` and writes only its profile and workflow drafts. |
| [R-18](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-18) | `7b9c849`, `d0b2052`, `b1832e0`, `3aa2439` | `lib/use-submit.ts` sends one write at a time and holds its key per target until an accepted reply settles it; a refused resend stays held, a held write's inputs stay locked, and another choice for a held target sends nothing (D2). Pause and Resume share the run as their target and Cancel has its own. The hold rules are pure functions in `lib/submit.ts`. One `AdmissionMessage` announces admission, and an unknown model is refused rather than becoming the default. |
| [R-19](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-19) | `f1bd3f5`, `b8323ba`, `d0b2052`, `b1832e0` | One CSRF token per browser session, resent once after a token refusal. The builders' keyed writes, approval decisions, the three unkeyed builder writes and the five settings save flows use the submit hook, with one refusal table per screen. |

## Review

An independent read-only reviewer (`autobots-reviewer`) inspected each wave's diff. A reviewer ran nothing; verification below is the coordinator's.

- **Wave 0 (R-01 to R-07):** changes needed, answered in `4e92b44`; the re-review's findings were answered in `848fcb3`.
- **Waves 1 and 2 (R-08 to R-12, R-17 to R-20), on `b8323ba`: changes needed.** Three blocking findings: a refusal of a resent request dropped the held key, so a lost reply could still start a second paid run or record a charge twice; the approval and effect screens could resend the other choice; and the spawned search child re-imported the caller's main module and wrote its arguments on the event loop. Should-fix: edits after a lost reply were silently discarded, planned browser cases were missing, the grant guard missed common forms, and four plan steps were undone. Answered in `d0b2052`.
- **Re-review of `d0b2052`: changes needed.** Blocking: a held run command could outlive a later accepted one, and three inputs weren't locked. Should-fix: the description save, test gaps, and a multi-schema default grant. Answered in `b1832e0`.
- **Re-review of `b1832e0`: changes needed, nothing blocking.** A lost Pause blocked Cancel until a reload, and the CPU-limit signal assumed macOS. Answered in `3aa2439`.
- **Re-review of `3aa2439`: approve.** One cosmetic note, kept under Limits.

The `db` run that preceded the last fixes also exposed three failures the review hadn't: the catalog check read pg_net's `net` schema, the code-search child re-ran the web tools check (the spawn problem above), and a browser case's arranged refusals lacked the error envelope. All three are fixed and observed passing below.

## Verification

All at `3aa2439`, with no edit during any run.

| Check | Exit | Observed |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed: harness 323 tests, service pytest (947 collected), API client 48, web unit 86, ruff, mypy, repository ruff and mypy, ESLint, Prettier, typegen, typecheck, contract drift, non-mutation guard |
| `python3.12 scripts/verify.py --profile db` | 0 | Passed: app_db 552 of 552 cases and identity 678 of 678, including the catalog checks, the R-17 denials, the code-search gateway cases, "after a lost Pause, Resume sends nothing, and Cancel still stops the run", "after a lost Approve, Reject sends nothing", the session and Run-this-version double clicks, the charge whose reply is lost after it reached the API, and the overlapping writes under one CSRF token |
| `python3.12 scripts/verify.py --profile operations` | 0 | Passed: operations 70, backup 50 and upgrade 45 cases on new disposable Compose projects with a scripted model; the upgrade qualifier applies migration 54 to an older install |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed, after this record |

Earlier runs on intermediate commits are superseded by these. One `db` run on `b1832e0` was stopped by hand, since its commit was about to change.

## Runbook

No operating procedure changed. A persistent install receives migration 54 only through the guarded apply (`make migrate`), then needs the web app rebuilt and the service restarted; nothing here touched it.

## Limits

- Static, mock and disposable evidence only. Nothing was checked on the persistent install, and none of this establishes H1 or product acceptance.
- A hold lives in one screen: a reload or navigating away ends it, which is how the person sees what happened (D2). The run panel's own "Reload the panel" button doesn't end it.
- "Publish draft" resends the stored draft's publish. If the first press never arrived and a newer draft was saved in between, the resend publishes the newer draft.
- Two tabs opening at once with no CSRF cookie can each mint a token, and the later write is refused once and resent.
- Approvals and unknown effects still announce refusals with `role="status"`.
- If an inherited hard CPU limit is at or below the requested soft limit, Linux ends the search child with SIGKILL, shown as `search_failed` rather than `search_timeout`. The CPU-limit test ran on macOS only.
- The catalog showed pg_net's `net.http_request_queue` and `net._http_response` deletable by the runtime role. They are outside the app's schemas and nothing here uses them, so the check now excludes them; whether to revoke that is a separate decision.
- Not done, with reasons in Decision 0027: pydantic as a direct dependency (D5), ESLint outside the web app (D7), formatting repository Python (D8), R-17's optional step 5 and the R-12 docstrings left to later items (D9).
- Two disposable Docker projects remain: `autobots-disposable-3b0abbba`, from the `db` run stopped by hand, and `autobots-disposable-cb16aed9`, three days old and not from this work. The project's hooks reserve volume removal for the guarded maintenance workflow, so they were left for the owner.
