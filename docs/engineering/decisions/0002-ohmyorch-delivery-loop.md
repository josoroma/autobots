# Decision 0002: run epic delivery through the OhMyOrch plugin

**Date:** 2026-11-04. **Authority:** explicit user request in this session: use OhMyOrch locally to implement epic loops with `deliver` from `SPECS.md`. **Supersedes in part:** [Decision 0001](0001-ohmyorch-adaptation.md), only its "do not install the upstream plugin or import its OpenSpec/archive/continuation machinery" clause. Everything else in 0001 stands.

## Decision

Epic and story delivery runs through the real upstream `ohmyorch` plugin, pinned to the commit recorded in `.claude/autobots.json` and installed from the local checkout at local scope. A delivery target is authorized only when the user names it on `/ohmyorch:deliver`.

The project-local harness is kept, not replaced. `scripts/specs.py`, `scripts/verify.py`, the project hooks and the read-only `autobots-spec-ingestor` keep their roles and run alongside the plugin.

## Commit policy

**Decided by the user on 2026-11-04:** work on a delivery branch named for the target, such as `delivery/epic-1`. Commit this setup first, then one commit per delivered story after `mark-done`. Do not push, rebase or squash without a further request. Without commits, a story's diff also contains every earlier story and this setup, so review has no story-bounded input.

## What this does not authorize

The boundaries in `AGENTS.md` are unchanged. No application model call outside the OpenRouter gateway, no paid qualification, no persistent reset or volume removal, no cloud project linking, no change to developer-client model credentials. Naming an epic authorizes that epic's stories as written, not new requirements.

## Where the two systems disagree

The bridge rule in [`.claude/rules/ohmyorch-delivery.md`](../../../.claude/rules/ohmyorch-delivery.md) resolves each of these for the coordinator.

| Upstream behavior | Project contract | Resolution |
|---|---|---|
| `BLOCKED` always escalates to a human | `BLOCKED` also means "story dependencies not DONE yet"; `READY` requires them DONE | `specs.py promote` moves only dependency-blocked stories to `READY`. `External:` blockers and open questions still stop the loop |
| The first non-`DONE` story in `SPECS.md` order is always next | US-2.3 and US-4.3 depend on stories later in their own epic | Not a product decision: stop the goal, deliver the prerequisite as its own target, resume the epic. The backlog is not reordered |
| `select` creates the change, then edits `SPECS.md` | The planning-handoff guard treats `SPECS.md` as product code while a change has no plan, so that order blocks itself | Edit `SPECS.md` first, while no change is active, then create the change. No guard is skipped |
| The context-preflight guard blocks `SPECS.md` edits once HEAD passes CODEBASE's recorded revision | Backlog status must still be editable after a commit | Refresh `CODEBASE.md` from the diff and record the new revision before the edit. That is what the guard asks for |
| The completion gate passes `UNVERIFIED` rows and an unrun OpenSpec verify, and does not bind verdicts to the final diff | DH-W06: required checks stay unpassed until actual evidence exists, and changed inputs invalidate evidence | The DH-W01–06 records, full verified coverage, a passing `harness` verification and `scripts/story_manifest.py compare` are required before `archive`. Upstream's gate alone is not sufficient |
| `delivery reopen` accepts only a blocking review or failing test report | A gap found after both pass must not be archived, and any fix invalidates the verdicts | Record the goal `BLOCKED` with `delivery block --reason`. A human decides the remediation, then a fresh blocking review makes `reopen` valid |
| Reviewer and tester may write only their own verdict file | DH-W03 needs reviewer identity, fingerprint and dispositions, and review must cover evidence | The coordinator persists DH-W records, copying specialist output. The tester exercises the runbook, and `autobots-reviewer` reviews the evidence summary and runbook before `archive` |
| Generic `ohmyorch:*` specialists | Layer rules and `autobots-*` roles | The bundled specialists own loop actions, because role checks use their identity. Whether project rules reach them is unqualified, so delegation prompts carry the applicable requirements |

The DH-W requirements are coordinator rules, not mechanical gates; independent review must surface a skipped record.

## Limits and known risk

- Upstream version `0.0.1` states that live delegated-agent identity and the full story lifecycle are still unproven. Treat the first delivered story as qualification of the loop itself, and report upstream defects rather than patching the pinned checkout.
- The plugin guards see `Write`, `Edit` and `MultiEdit`; shell writes can bypass them. They are workflow guardrails, not confinement.
- `guard-story-done` only protects a story with an active change. In a fixture, setting `DONE` on a story that never had a change was allowed. `specs.py validate` still rejects `DONE` with unticked tasks, but nothing mechanical requires a change or evidence first. Only the loop's derived actions and independent review catch that.
- Upstream defects found by review, not patched: `completion-gate.sh:197` tests `$COND_STATE[1]`, which never equals `pass` in Bash, so its review-contract check never runs. Review also reports that `guard-archive.sh` lets that verdict override `workflow-status`, so an archive run ahead of the derived action could skip gate failures. Follow the derived action and the bridge's archive conditions.
- `promote` lifts a bare `BLOCKED` hold on a story whose dependencies are all `DONE`. Human holds must be recorded as an open question or `External:`.
- The work item lists what has and has not been exercised. Fixture runs of hook scripts do not prove live event delivery or role identity.
- Upstream has no selected distribution license. The plugin is used locally and not redistributed from this repository.

## Reversal

`claude plugin uninstall ohmyorch@ohmyorch-marketplace --scope local` removes the plugin and leaves project state. `bootstrap` reports a recovery ID for its writes; [the runbook](../runbooks/ohmyorch-delivery.md) records how to inspect and roll them back.
