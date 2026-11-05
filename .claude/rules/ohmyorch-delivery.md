# OhMyOrch delivery bridge

Applies while coordinating `/ohmyorch:deliver` in this project. [Decision 0002](../../docs/engineering/decisions/0002-ohmyorch-delivery-loop.md) explains why. Follow the plugin's derived next action, with these additions, in this order. Never patch the pinned upstream checkout or bypass a guard, including by editing a guarded file through the shell. The one exception is `scripts/specs.py`, which rewrites `SPECS.md` only for `render` and `promote`, as written below.

Bundled specialists are not guaranteed to see this file. Put the applicable requirements from it, and the story's IDs and paths, in each delegation prompt.

Checks for this rule: [`scripts/verify.py`](../../scripts/verify.py), [`scripts/specs.py`](../../scripts/specs.py) and [`scripts/story_manifest.py`](../../scripts/story_manifest.py). Review: `ohmyorch:reviewer` for the verdict and [`autobots-reviewer`](../agents/autobots-reviewer.md) for the evidence review.

## Before starting a goal

- `git -C research/upstream/OhMyOrch rev-parse HEAD` must equal `upstream.commit` in `.claude/autobots.json`.
- `gitCommitSha` for this plugin in `~/.claude/plugins/installed_plugins.json` must equal it too, and its cached `installPath` must match `research/upstream/OhMyOrch/plugins/ohmyorch` under `diff -r`. A cached copy exists, and a live hook was observed running from the checkout, so both must be the pinned code.
- The commit policy in Decision 0002 must be recorded, and the working tree must hold no other uncommitted work. Otherwise a story's changed files include unrelated work.

## `select`

1. **If HEAD moved past `Analyzed revision` in `CODEBASE.md`:** update `CODEBASE.md` from an analysis of `git diff --name-only <recorded>..HEAD`, including the note under the revision saying what it covers. Then set the revision to the current HEAD. Keep the `Current capabilities` heading, because stories link to it. Otherwise the context-preflight guard blocks every `SPECS.md` edit. Its suggested `staleness accepted` line does not unblock it, and `unknown` silently disables the guard, so use neither. Never rebase or squash a recorded revision away, because the guard then silently stops checking.
2. Edit `SPECS.md` while no change is active: `Status: IN PROGRESS`, with the `Change:` line directly below it. Upstream lists `openspec new change` first, but then its planning-handoff guard rejects this edit.
3. Run `python3.12 scripts/specs.py render`, then `validate`.
4. Run `openspec new change <id>`, then the plugin's `status --change <id>`.

## `plan`

Tell the planner to list `SPECS.md`, `CODEBASE.md`, `openspec/changes/<id>/` and the story's work-item, evidence and runbook paths, so scope checks do not report routine files as unpredicted. Tell the reviewer the same.

Also have the plan name what the story's tests and builds generate. Generated output must be Git-ignored before capture, or it fails `compare`. A story that adds tooling adds its ignores. Generated files that are part of the contract must not be ignored, because ignored files are not covered.

## Records: the coordinator owns them

The reviewer may write only `review.md` and the tester only `test-report.md`, and an implementer recording its own review would breach DH-W03. So the coordinator persists every DH-W record, copying specialist output rather than rewriting it.

| When | Record |
|---|---|
| After `implementation-plan.md` exists, before `implement` | Open `docs/engineering/work-items/<US-id>.md` with the plan. The guard blocks most writes outside `openspec/` and `.claude/` until the plan exists |
| After `implement`, before capture | Implementation section: changed paths, actual behavior, deviations. Finish the runbook entry here, or identify the existing verified procedure and its regression check (DH-W05). It must be final at capture: its text links to the story's evidence, which holds the last-exercised revision, date and result the Option B contract requires for a verified claim |
| After `test` | Review section: reviewer identity, reviewed fingerprint, findings and dispositions. Evidence summary under `docs/engineering/evidence/<US-id>/`, recording which runbook steps were exercised and which remain untested, and distinguishing mocked, static, disposable and live results |
| After `mark-done` | Links to verdicts at their archived path, written before the final verification |

## Protected paths

Upstream's write scope stops `ohmyorch:implementer` from writing `.claude/*`, `AGENTS.md`, `CLAUDE.md`, `README*`, `.gitignore`, `openspec/*`, the mapped PRD, `SPECS.md` and `CODEBASE.md`. When a story's acceptance needs such a file, as US-1.2 and US-1.4 do, the user decided on 2026-11-04 that:

1. The plan names each protected path. Without that, stop and report.
2. The implementer authors the content and returns it under a heading naming the exact path, stating what it could not test because the file was not yet in place.
3. The coordinator writes it verbatim, before capture, and records in the Implementation section which paths were persisted this way. The coordinator does not edit that content. A needed change goes back to the implementer.
4. The reviewer checks these files as implementation. The coordinator is not their reviewer.

This covers implementation content only. Verdicts, `goal.md`, `status.md` and `completion.md` stay with their owners, and `SPECS.md` and `CODEBASE.md` stay coordinator-owned. Never use it to change a guard, a hook registration's protection or a story's acceptance. Those need explicit user authority, and a plan cannot grant it.

## `review` and `test`

Capture immediately before every `review`, including after a reopen. If verification or capture fails, do not delegate: a stale manifest may still be on disk. Run `delivery block --reason` and report it.

```sh
python3.12 scripts/verify.py --profile harness && python3.12 scripts/story_manifest.py capture <US-id>
mkdir -p .checks/<US-id> && jq -r '.files | keys[]' docs/engineering/evidence/<US-id>/reviewed-manifest.json > .checks/<US-id>/changed.txt
```

Give the reviewer the manifest, its fingerprint and `changed.txt`, because `git diff` omits untracked files. Use `check-scope --diff .checks/<US-id>/changed.txt`. Never pipe into `check-scope`: it reads non-terminal stdin as the file list.

Give the tester the same fingerprint. Both must state it, since it is the only trace of a recapture, on its own line exactly as `Reviewed fingerprint: <hex>`. Never add it to the `Verdict:` or `Blocking:` line or to a criterion row: upstream's validators and gates parse those, and `Blocking: None (fingerprint …)` would derive a false `reopen`. Delegate exercising the runbook to the tester, with results in `test-report.md`. The coordinator does not test.

## Evidence review, before `archive`

Verdict authors never see the evidence summary. Delegate a read-only review of the work item, evidence summary and runbook to `autobots-reviewer`, with the manifest and test report. It must confirm that the `Reviewed fingerprint:` lines in `review.md` and `test-report.md` match the manifest. Record its findings and dispositions in the work item.

## `archive`

The upstream completion gate is necessary but not sufficient. All of these must hold:

- The evidence review has no unresolved blocking finding.
- `test-report.md` covers every scenario and has no `UNVERIFIED` row, apart from the one exception below. Upstream's gate passes `UNVERIFIED` rows and `OpenSpec verify: not run`, and neither otherwise qualifies here.
- **Unmet-Given exception, decided by the user on 2026-11-04:** a scenario whose Given is explicitly conditional, such as "Given X is absent", and does not hold today is scored `UNVERIFIED`, never `PASS`. Archive may proceed only if the row states the Given does not hold, re-run probes evidence that, and the evidence summary and work item name the scenario as unexercised.
  - **Confirmed by the user on 2026-11-04, for all stories:** an "any required item is absent" Given holds if any such item is absent, and a recorded decision that one item is not required only removes that item.
  - **Confirmed by the user on 2026-11-05, for all stories:** the exception does not cover a scenario exercising behavior the story implements, when a disposable environment can arrange its precondition. Arrange it and score from what is observed, stating plainly that the condition was arranged, not naturally present.
  - **Coordinator's wording, not put to the user:** a scenario merely hard to run does not qualify.
- `python3.12 scripts/verify.py --profile harness` passes, reported as harness evidence only.
- `python3.12 scripts/story_manifest.py compare <US-id>` passes, with its output recorded in the evidence. It fails on any change since capture, except records written after review and Git-ignored files. Never recapture to make it pass. Between this check and the story commit, change nothing but records and what the `archive` and `mark-done` steps themselves change.

If any fails, do not archive. `delivery reopen` only accepts a blocking review or failing test report, and the gates do not bind verdicts to the final diff, so editing code now would leave stale verdicts passing. Run the plugin's `delivery block --reason "<what failed>"` and report the decision needed.

To resume once a human has decided: delegate the reviewer with the failed condition. Its blocking finding makes `delivery reopen` valid, which preserves the verdict and adds remediation tasks. Then implement, capture, review and test again. Any runbook, plan or source edit after capture takes this route, because the runbook was exercised as captured. Only an evidence summary or work-item fix avoids it, since those are records: correct the record and rerun the evidence review.

## `mark-done`

Tick the story's tasks and set `Status: DONE` in one edit, because `render` rejects `DONE` with unticked tasks. Add the archived-path links. Then, before asking for the next action:

```sh
python3.12 scripts/specs.py render && python3.12 scripts/specs.py promote && python3.12 scripts/specs.py validate && python3.12 scripts/verify.py --profile harness
```

Record the final `input_fingerprint` and `input_manifest` in the story's evidence. Evidence is excluded from the fingerprint, so this does not invalidate it. Then commit the story under the recorded commit policy.

`promote` moves `BLOCKED` to `READY` only when every declared story dependency is `DONE` and the story has no `External:` dependency, open question or prose on a dependency line. It would lift a bare `BLOCKED` hold, so a human hold must be recorded as an open question or `External:`. Never hand-edit a story to `READY` to keep the loop moving.

## When the next story stays `BLOCKED`

Compare its dependencies with the backlog:

- **An `External:` dependency, open question or `NEEDS CLARIFICATION`:** a real decision. Stop and report it.
- **Any undelivered story dependency:** an ordering artifact, not a product decision, because upstream always takes the first non-`DONE` story of the target. Run the plugin's `delivery stop`, deliver the prerequisite with `/ohmyorch:deliver <US-id>`, then resume with `/ohmyorch:deliver <EPIC-N>`. Within an epic this currently affects US-2.3 (needs US-2.4, US-2.5) and US-4.3 (needs US-4.4). Do not reorder the backlog without explicit authority.

## Stopping

Stop when a story would need a paid model call, a live credential, a persistent database change or reset, a cloud project link, a missing tool, or a decision its sources do not make. These are not derived `escalate` actions, so ending the turn only makes the Stop hook block until it records a misleading "no progress". Run `delivery block --reason "<decision needed>"`, then report.

Disposable, target-guarded Docker fixtures that a story itself requires are in scope. Dependency installs are in scope only when the story being delivered requires them, and they are pinned and recorded. A skipped check, template or fixture never satisfies acceptance.

## After every `SPECS.md` status or task edit

Run `python3.12 scripts/specs.py render`, then `validate`. Stale navigation fails validation.

## Reporting

A delivered story means its acceptance has current evidence, apart from any scenario closed under the unmet-Given exception, which is reported as unexercised. It does not establish H1 or product acceptance unless that story's own gates say so.
