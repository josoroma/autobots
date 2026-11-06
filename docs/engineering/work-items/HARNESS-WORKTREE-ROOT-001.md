# HARNESS-WORKTREE-ROOT-001 — Hook root for a session in a worktree

Status: IN PROGRESS
Evidence: this record. No manifest or `summary.md` yet, so DH-W04 and DH-W06 are not met and this cannot close as it stands.

## Plan

DH-W01. No `SPECS.md` story owns this. It was requested after `fc31228` confirmed that hooks in a worktree session evaluate the main checkout.

- **Intended behavior:** a session in a worktree under `.claude/worktrees/` is guarded, classified and checked against that worktree.
- **Invariant:** hook input selects a root only from a fixed set, and the guard's root is never wider than the dispatcher's own checkout. Input still decides which member of that set applies, and so whose reports `Stop` reads.
- **Verification:** real Git fixtures in `tests/harness/test_hooks.py`, including forged `cwd` values, and the `harness` profile.

## Implementation

DH-W02.

- **Changed paths:** `.claude/hooks/dispatch.py`, `tests/harness/test_hooks.py`, [the harness runbook](../runbooks/development-harness.md#which-checkout-a-hook-evaluates) and `CODEBASE.md`. It builds on `fc31228`.
- **Actual behavior:** `session_root` chooses the innermost worktree Git registers strictly inside the dispatcher's `.claude/worktrees/` that holds `cwd`, otherwise the dispatcher's checkout. `handle` asks for it per event. If Git fails or takes over 2 seconds for a `cwd` there, a file edit is denied with a reason, `PostToolUse` says so, and `Stop` blocks once per turn. Only those three events ask Git.
- **Rejected:** trusting `cwd` as given, which lets input move the guard outside the checkout. Running the worktree's copy of the hook, which lets input choose the enforcing code. Refusing edits under `.claude/worktrees/` from the main root, which `cd` into a sibling bypasses anyway. Falling back to the main root when Git cannot answer, which is wider than the worktree the session may be in. Exiting 2 for every event when Git cannot answer, which the second review showed traps a session in a `Stop` loop with `Bash` blocked.
- **Deferred:** live event delivery stays with the adapter's separate qualification.
- **Decided by the user, 2026-11-06:** `Stop` in a new worktree keeps wanting its own current `fast` or `full` and `db` reports, so an unbootstrapped worktree blocks once at the end of each turn. Main-checkout reports do not count for a worktree. It is recorded in the runbook as a limit.

## Review

DH-W03.

- **Author and reviewer:** the implementing session; `autobots-reviewer`, in a separate read-only context, over two passes.
- **First pass, fixed:** the stated invariant was too strong, and `cd` in each direction was undocumented. A new worktree's `Stop` cost was understated and untested. A Git failure silently gave the wider root. The Git timeout and deadline had no test that could fail. `.claude/worktrees` itself could be a root. A locked worktree with a missing directory could be a root. Runbook wording on `ruff`, version skew and the repository Git reads.
- **Second pass, fixed:** two blocking findings. The first pass's fix exited 2 before `stop_hook_active` was read, so a lasting Git failure looped `Stop` and blocked `Bash`, and the runbook misdescribed it and gave an impossible recovery. Also weak test oracles, the untested `db` half of a new worktree's `Stop`, and Git searching above the checkout.
- **Left:** a deadline signal arriving inside path resolution can be swallowed, because `TimeoutError` is an `OSError`. `resolve_path` already had this trait, but its use in `session_root` is new, and there it can give the wider root with no deadline left. `realpath` swallows it where the dispatcher cannot catch it. The 10-second hook timeout still applies.
- **Left:** `guard` resolves the root again, so swapping a worktree for a link between selection and the check would widen it. `Bash` can write there anyway.
- **Not reviewed:** the fixes after the second pass, which are the per-event handling above and its tests. Mutation checks cover them, but no independent reader has. No fingerprint is bound.

## Verification

DH-W04. Static and disposable-fixture classes only.

- **Not exercised:** a real Claude event carrying `cwd`. The running session still uses the main checkout's old hook code, so this change has guarded nothing live.
- **Observed by synthetic payload on the real repository, before the change:** the main checkout's dispatcher classified a worktree's `scripts/harness_lib.py` as `harness`, and allowed edits to the main checkout and a sibling from a worktree `cwd`.
- **Observed the same way with this change, with the main checkout as home:** from the worktree, edits to its own files were allowed and edits to the main checkout and a sibling denied, and `scripts/harness_lib.py` classified as `db, python, web`. From the main checkout, an edit there was allowed. A `cwd` of `/private/tmp` could edit the main checkout, as before, and not `/private/tmp`.
- **Checks:** `python3.12 scripts/verify.py --profile harness` exit 0, with 236 behavior tests. It proves repository checks only. `fast`, `db` and `operations` were not run, because this changes none of their inputs' behavior.
- **Mutation:** each validation and failure path was removed in turn, and each removal failed `test_hooks.py`. The first attempt left two survivors: one was dead code, since removed, and one was an untested filter, since tested.

## Runbook

DH-W05. [Which checkout a hook evaluates](../runbooks/development-harness.md#which-checkout-a-hook-evaluates).
