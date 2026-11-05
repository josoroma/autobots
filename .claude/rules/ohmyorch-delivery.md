# OhMyOrch delivery

Applies while running `/ohmyorch:deliver`. [Decision 0003](../../docs/engineering/decisions/0003-openspec-only-delivery.md) explains why. The main session follows OpenSpec's lifecycle directly, with no specialist agents and no review rounds: `select` → `propose` → `implement` → `verify` → `archive` → `mark-done`. Follow the plugin's derived next action.

Checks for this rule: [`scripts/verify.py`](../../scripts/verify.py) and [`scripts/specs.py`](../../scripts/specs.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md), only when the user asks for one or a story's own acceptance requires it.

## Records

The OpenSpec change is the record: `proposal.md`, `specs/`, `tasks.md`, optional `design.md` and `verification.md`, kept when archived. Keep them short. No per-story work item or evidence directory, unless a story's acceptance asks for one.

## Each story

1. Keep `CODEBASE.md` and its `Analyzed revision` honest when a story changes what it describes. Files in a change such as `implementation-plan.md`, `review.md` or `test-report.md` are ignored.
2. `select`: set `Status: IN PROGRESS` with the `Change:` line directly below it, then `python3.12 scripts/specs.py render` and `validate`.
3. `verify` (`/ohmyorch:opsx-verify`, recorded in the change's `verification.md`): run the story's checks, and score each scenario from what was run. A `MISMATCH` or `NOT VERIFIED` returns to `implement`. Never report a scenario as passing without observing it. An `UNVERIFIED` scenario stays visibly unexercised.
4. Before `archive`: `python3.12 scripts/verify.py --profile harness` passes, reported as harness evidence only. Archive is a standalone CLI call, alone in its command, so the guard can see it.
5. `mark-done`: tick the story's tasks and set `Status: DONE` in one edit, then `python3.12 scripts/specs.py render && python3.12 scripts/specs.py promote && python3.12 scripts/specs.py validate`.
6. Commit one story on the delivery branch. Do not push, rebase or squash without a request.

`promote` moves `BLOCKED` to `READY` only when every declared story dependency is `DONE` and the story has no `External:` dependency, open question or prose on a dependency line. Never hand-edit a story to `READY` to keep the loop moving.

## Conditional scenarios

Decided by the user. A Given such as "required items are absent" holds if any required item is absent, and a decision that one item is not required removes only that item. A scenario exercising behavior the story implements is arranged in a disposable environment when its precondition is not naturally present, scored from what is observed, and reported as arranged. A conditional Given that truly does not hold, and that nothing can arrange, is `UNVERIFIED`, never `PASS`.

## When the next story stays `BLOCKED`

- **An `External:` dependency, open question or `NEEDS CLARIFICATION`:** a real decision. Stop and report it.
- **Any undelivered story dependency:** story order, not a product decision. Run `delivery stop`, deliver the prerequisite with `/ohmyorch:deliver <US-id>`, then resume the epic. Within an epic this currently affects US-2.3 (needs US-2.4, US-2.5) and US-4.3 (needs US-4.4). Do not reorder the backlog without explicit authority.

## Stopping

Run `delivery block --reason "<decision needed>"` and report when a story would need a paid model call, a live credential, a persistent database change or reset, a cloud project link, a change outside this repository, a missing tool, or a decision its sources do not make.

Disposable, target-guarded Docker fixtures a story requires are in scope. Dependency installs are in scope only when the story requires them, repo-local, pinned and recorded. A story that introduces a tool adds that tool's ignores. A skipped check, template or fixture never satisfies acceptance.

## Reporting

A delivered story means its scenarios were observed by the main session, with no independent review unless stated. It does not establish H1 or product acceptance unless that story's own gates say so.
