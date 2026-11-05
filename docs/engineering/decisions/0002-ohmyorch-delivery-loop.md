# Decision 0002: run epic delivery through the OhMyOrch plugin

**Superseded in part by [Decision 0003](0003-openspec-only-delivery.md)** for delivery gates, roles and records. The tables below describe the earlier process.

**Date:** 2026-11-04. **Authority:** explicit user request in this session: use OhMyOrch locally to implement epic loops with `deliver` from `SPECS.md`. **Supersedes in part:** [Decision 0001](0001-ohmyorch-adaptation.md), only its "do not install the upstream plugin or import its OpenSpec/archive/continuation machinery" clause. Everything else in 0001 stands.

## Decision

Epic and story delivery runs through the real upstream `ohmyorch` plugin, pinned to the commit recorded in `.claude/autobots.json` and installed from the local checkout at local scope. A delivery target is authorized only when the user names it, on `/ohmyorch:deliver` or in a request. See "Delivery targets" below.

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
| The completion gate passes `UNVERIFIED` rows and an unrun OpenSpec verify, and does not bind verdicts to the final diff | DH-W06: required checks stay unpassed until actual evidence exists, and changed inputs invalidate evidence | The DH-W01–06 records, verified coverage apart from the unmet-Given exception, a passing `harness` verification and `scripts/story_manifest.py compare` are required before `archive`. Upstream's gate alone is not sufficient |
| `delivery reopen` accepts only a blocking review or failing test report | A gap found after both pass must not be archived, and any fix invalidates the verdicts | Record the goal `BLOCKED` with `delivery block --reason`. A human decides the remediation, then a fresh blocking review makes `reopen` valid |
| Reviewer and tester may write only their own verdict file | DH-W03 needs reviewer identity, fingerprint and dispositions, and review must cover evidence | The coordinator persists DH-W records, copying specialist output. The tester exercises the runbook, and `autobots-reviewer` reviews the evidence summary and runbook before `archive` |
| Generic `ohmyorch:*` specialists | Layer rules and `autobots-*` roles | The bundled specialists own loop actions, because role checks use their identity. Whether project rules reach them is unqualified, so delegation prompts carry the applicable requirements |

The DH-W requirements are coordinator rules, not mechanical gates; independent review must surface a skipped record.

## Decisions made while delivering US-1.1

By the user on 2026-11-04, except where marked. The protected-path, unmet-Given and "any required item" decisions are also in the bridge rule, because they govern later stories. The others are recorded here.

- **Protected paths:** `ohmyorch:implementer` cannot write `.claude/*`, `AGENTS.md`, `CLAUDE.md`, `README*`, `.gitignore`, `openspec/*`, the mapped PRD, `SPECS.md` or `CODEBASE.md`, yet US-1.2 and US-1.4 are largely about such files. When a plan names one, the implementer authors the content, the coordinator writes it verbatim, and the reviewer checks it as implementation. The upstream guard is unchanged.
- **Unmet Given:** a conditional scenario whose Given does not hold is scored `UNVERIFIED`, never `PASS`, and may be archived only under the bridge rule's stated conditions. This is the one exception to "no `UNVERIFIED` row"; the scenario stays visibly unexercised.
- **Local transcripts (US-1.1 only):** DH-03 says to ignore them, but no source names an in-repository location. They are recorded as not missing, with no rule added, and the inventory states the gap.
- **Cache ignores (US-1.1):** DH-03 says to ignore caches with no in-use limit, so five categories with no rule (`.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo`, `.pnpm-store/`) are added in US-1.1 through the reopen route, not deferred to US-1.3. These five close the cache question for US-1.1. Other caches also have no rule and are not claimed as covered: a later story that introduces a tool adds that tool's ignores, and reviewers enforce that.
- **"Any required item":** a Given such as "required ignores are absent" holds if any required item is absent, and a decision that one item is not required removes only that item. Confirmed for all stories.
- **Arranged preconditions, 2026-11-05:** the unmet-Given exception does not cover a scenario exercising behavior the story implements, when a disposable environment can arrange its precondition. It is arranged and scored from observation, stating that the condition was arranged. The bridge's "merely hard to run" clause remains the coordinator's wording, unconfirmed.
- **Research payload files:** `research/qwen38-gguf-probe.json` and `research/qwen38-gguf-performance.json` hold model request and response payloads. They are historical experiment evidence, not DH-03 local transcripts, and stay tracked. Their message text has not been read.
- **Runbook exercise status, 2026-11-05:** the runbook links to the story's evidence, which states last-exercised revision, date, result and what is untested. This departs from SP-018's literal wording, and the user confirmed it, because recording results in the runbook after testing would invalidate the review.
- **Rigor, 2026-11-05:** from US-1.3 on, the architect critique and adversarial checks run only on stories with real risk. The rule's required gates stay on every story.
- **Provider SDKs in the lock, 2026-11-05:** `deepagents` 0.7.32 hard-requires `langchain-anthropic` and `langchain-google-genai`, while DH-01 says this milestone adds no Anthropic SDK. They are locked as unused transitive dependencies. Owned code never imports them, a test enforces it, and application inference stays OpenRouter-only.
- **Node and pnpm, 2026-11-05:** Node is pinned to 22.23.2. pnpm is repo-local through Corepack, without `corepack enable`. No change outside this repository.
- **Delivery targets:** on 2026-11-04 the user asked to "loop delivery one epic by epic until complete all", which the coordinator reads as naming every epic; that reading is the coordinator's. This does not lift the boundaries above: US-3.4's paid qualification and US-7.2's choice of service remain the user's decisions, and the loop stops there.

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
