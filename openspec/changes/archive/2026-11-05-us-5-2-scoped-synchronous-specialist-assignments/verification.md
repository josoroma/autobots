# Verification — us-5-2-scoped-synchronous-specialist-assignments

Change: us-5-2-scoped-synchronous-specialist-assignments
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `78d8759`, working tree with this change. A real Deep Agents graph with a scripted model, real Postgres and real Storage on a disposable stack, and a real killed process. `scripts/qualify_identity.py` exit 0, 163 cases. `scripts/app_db.py types`: 335 cases passed. `--profile full` passed.

## Scenarios

**Narrow child execution: observed.**
- A child ran to a verified result. It records its parent and root, and the parent got references only, with the child's files staying in the child's run.
- Its tools are the intersection with the parent. A tool the Expert has and the parent lacks is `tool_not_granted`. Asking for more than the parent holds is `scope_expansion_denied`, with no child. An Expert outside the session is `route_not_granted`.
- Its paths are the parent's `inputs` and its own `outputs/child-1`.
- Its policy snapshot equals the parent's, so its Expert's own model binding doesn't apply.
- A child at the depth limit has no delegation tool. A second child past a limit of 1 is `children_limit`, and an outstanding limit is enforced.
- With a limit of 3 calls, the parent's 2 and the child's 1 used it up, and the next call was refused. Its calls are reserved on the root's ledger, so the root's spend limit covers them. The time limit reads the root too, from the code, with no case of its own.

**Reattach after replay: observed, with a real killed process.**
- The model repeating a request gets the same child and result.
- A parent process killed by SIGKILL inside its child's model call: after an arranged lease expiry, the replacement replayed the tool without a model call, found the child, classified its open call as uncertain, and paused with `assignment_paused`. There was still 1 assignment.
- After the call was reconciled and the parent resumed, the same child finished under its own new generation.
- During a child's model call the parent has 0 open model invocations, so it holds no slot.

Also observed: cancelling a parent during its child's call cancels both in one transaction, no new call starts, and the child's next effect never happens.

## Findings

- **Not exercised:** a parent paused while its child runs (`parent_not_running`), a resume that restarts a child paused by that route, and two levels of delegation with real children. No browser test covers the Assignments card on the run page, only type checks.
- **The whole parent connection waits on the child,** since children run inline. That's the PRD's synchronous MVP, and asynchronous specialists aren't built.
- **A child's allowance is the root's remainder,** since the sources state no per-child split. One child can use all of it.
- **Delegation is granted to any run in a coordinator session,** which is my reading of "coordinator". A direct session can't delegate.
- **No independent review.** EPIC-4's review found blockers in code that had passed checks like these.
