# OhMyOrch delivery

Applies while running `/ohmyorch:deliver`. [Decision 0003](../../docs/engineering/decisions/0003-openspec-only-delivery.md) explains why the main session delivers with no specialist agents and no review rounds, and [Decision 0030](../../docs/engineering/decisions/0030-ohmyorch-0-1-0-delivery.md) sets the plugin version. Each story is one OpenSpec change: `propose` → `apply` → `verify`, which ends with `archive` → `mark-done`. Follow the plugin's derived next action.

Checks for this rule: [`scripts/verify.py`](../../scripts/verify.py) and [`scripts/specs.py`](../../scripts/specs.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md), only when the user asks for one or a story's own acceptance requires it.

## Records

The OpenSpec change is the record: `proposal.md`, `specs/`, `tasks.md` and optional `design.md`, kept when archived. `tasks.md` is the only progress tracker. Keep them short. No per-story work item or evidence directory, unless a story's acceptance asks for one.

## Each story

1. Keep `CODEBASE.md` and its `Analyzed revision` honest when a story changes what it describes. Other files in a change, such as `verification.md`, `status.md` or `review.md` in older archived changes, are history the plugin ignores.
2. `propose` (`/ohmyorch:opsx-propose`): once the artifacts exist, set `Status: IN PROGRESS` with the `Change:` line directly below it, then `python3.12 scripts/specs.py render` and `validate`.
3. `apply` (`/ohmyorch:opsx-apply`): implement, and tick a task in `tasks.md` only when it is done.
4. `verify` (`/ohmyorch:opsx-verify`): run the story's checks, and score each scenario from what was run. Never report a scenario as passing without observing it. A scenario that is not implemented, contradicts its `Then` or has no observed evidence, and a check this change breaks, are CRITICAL: append each as an unticked task to `tasks.md`, which returns the change to `apply`. Verify writes no file, so report each scenario's score in the session and in the story's commit message.
5. Before archive: `python3.12 scripts/verify.py --profile harness` passes, reported as harness evidence only. Archive is `openspec archive <change> -y`, a standalone CLI call alone in its command, so the guard can see it.
6. `mark-done`: in one edit, tick the story's tasks, set `Status: DONE` and point `Change:` at the archived path. Then `python3.12 scripts/specs.py render && python3.12 scripts/specs.py promote && python3.12 scripts/specs.py validate`; `render` rewrites the `Work Item Status` table, so never edit it by hand.
7. Commit one story on the delivery branch. Do not push, rebase or squash without a request.

`promote` moves `BLOCKED` to `READY` only when every declared story dependency is `DONE` and the story has no `External:` dependency, open question or prose on a dependency line. Never hand-edit a story to `READY` to keep the loop moving.

## Conditional scenarios

Decided by the user. A Given such as "required items are absent" holds if any required item is absent, and a decision that one item is not required removes only that item. A scenario exercising behavior the story implements is arranged in a disposable environment when its precondition is not naturally present, scored from what is observed, and reported as arranged. A conditional Given that truly does not hold, and that nothing can arrange, is `UNVERIFIED`, never `PASS`. Having no observed evidence, it is CRITICAL in `verify` (Decision 0030), so stop as below and report it for the owner's decision.

## When the next story stays `BLOCKED`

- **An `External:` dependency, open question or `NEEDS CLARIFICATION`:** a real decision. Stop and report it.
- **Any undelivered story dependency:** story order, not a product decision. Run `delivery stop`, deliver the prerequisite with `/ohmyorch:deliver <US-id>`, then resume the epic. Within an epic this currently affects US-2.3 (needs US-2.4, US-2.5) and US-4.3 (needs US-4.4). Do not reorder the backlog without explicit authority.

## Stopping

Run `delivery block --reason '<story id: the decision needed>'` (single quotes, with no quotes, backticks or `$` inside) and report when a story would need a paid model call, a live credential, a persistent database change or reset, a cloud project link, a change outside this repository, a missing tool, or a decision its sources do not make.

Disposable, target-guarded Docker fixtures a story requires are in scope. Dependency installs are in scope only when the story requires them, repo-local, pinned and recorded. A story that introduces a tool adds that tool's ignores. A skipped check, template or fixture never satisfies acceptance.

## Reporting

A delivered story means its scenarios were observed by the main session, with no independent review unless stated. It does not establish H1 or product acceptance unless that story's own gates say so.
