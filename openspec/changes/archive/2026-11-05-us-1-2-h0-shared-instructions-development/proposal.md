# Proposal

Story: US-1.2
Change: us-1-2-h0-shared-instructions-development

## Why

SP-001 item 2, DH-03, DH-04 and DH-02 H0.2 require shared instructions and project assistant assets whose rules link to checks or review responsibilities. Most of those assets exist, but presence is not acceptance: six of the eight rule files and all of `AGENTS.md` link to no check and no review responsibility, several skills do not define every element DH-04 requires, nothing validates an unavailable or incompatible Claude adapter, and the ingestion evidence predates the current skill text and the delivery plugin.

## What Changes

- Link each `.claude/rules` file to a check or review responsibility, and give each rule-bearing section of `AGENTS.md` one mapping row, including Completion evidence and the Commands profile statement. `.claude/settings.json` cannot carry links, so the same table names `project_configuration` and the review skill as its responsibility. A harness check fails when a rule file or `AGENTS.md` loses this.
- Inspect every skill and agent against the DH-04 elements in a per-file table, before any protected content is authored, and close the gaps it finds. Skills and agents are covered by this table rather than by per-rule links.
- Add static checks for instruction links, frontmatter keys, representative rule paths and facts repeated across assets. Compare the copies of each common rule, before authoring and again on the final tree. A contradiction among authored assets must be fixed; it cannot pass by being listed.
- Add a derived adapter status to harness validation: `inactive` with a reason when Claude is unavailable, below the recorded minimum version, or its configuration is invalid, otherwise `configured_unqualified`. Never `active` or `qualified`. Print it in the runner's summary.
- Make validation reject any activation claim in the qualification fields and an unusable minimum version, and add negative fixtures for prompt or agent hooks and for model, environment or permission settings.
- Add `Change:` to the read-only ingestor's story grammar, because `SPECS.md` now uses that line and the ingestor does not know it, with a test that fails on the current text. Add tests for the read-only tool sets, the paired workflow and the retained forward fixture.
- Repeat the forward ingestion on a disposable copy of the fixture, arranged with synthetic `SP-*` coverage and a real story dependency, following the paired skill's steps. The real `SPECS.md` is not rewritten.
- Run paired good and broken controls of `claude plugin validate` during implementation, on the `.claude` shape and under `--strict` on a plugin-shaped scratch directory with a manifest, and record the observed results before capture.
- Update the development harness runbook, replacing its recorded last-exercise section with a link to the story's evidence, and record pinned provenance, the observed syntax results, what they do not show, and adapter limits in the adaptation page.

No new dependency, model provider, paid call, service or database. `.claude/settings.json`, `.claude/autobots.json` and `.claude/hooks/dispatch.py` are expected to stay unchanged.

## Observed Current State

Observed by the Planner on 2026-11-04 at base revision `9714930`. The Implementer and Tester re-probe; none of this is acceptance evidence.

| Item | Observed | Evidence | Remaining |
|---|---|---|---|
| Shared instructions | `AGENTS.md` exists. `CLAUDE.md` imports it and is short, apart from the plugin's managed block | Read | No links to checks or review |
| Required skills (DH-04) | All 12 required, plus `autobots-spec-ingest` | Read all 13 | No gap in presence. **Content gap on the Planner's reading:** seven skills lack relevant paths or failure behavior; see the plan's DH-04 table. No skill applies persistent operations, so `disable-model-invocation` has no user yet |
| Specialist agents (DH-04) | Architecture, Next.js, Python/workers, database, infrastructure and reviewer, plus the ingestor. Reviewer, architect and ingestor have only Read, Grep and Glob | Read all 7 | Planner's reading finds scope, tools, inputs and a result contract in each. Nothing tests the tool sets |
| Path-scoped rules (DH-03) | Web, Python, database, infrastructure and contracts, plus model gateway | Read | **Gap: see below** |
| Project settings and hooks | Five command hooks; `config_errors` enforces their shape and rejects non-hook settings | `scripts/harness_lib.py`, `tests/harness/test_hooks.py` | Prompt or agent hooks have no negative fixture |
| Instruction links | All Markdown links in rules, skills, agents, `AGENTS.md` and `CLAUDE.md` resolve, fragments included | One-off local script, not a retained check | No retained check |
| Frontmatter keys | Skills use `name` and `description`; agents also use `tools` and `model`; six rules use `paths` | Read; key count over all 20 skill and agent files | `config_errors` checks only that `name` and `description` exist. DH-03's "test representative paths" has no test |
| Backlog and fixture validation | `specs.py validate` passes: 10 epics, 42 stories, 86 tasks. The retained fixture passes: 1 epic, 4 stories, 13 tasks | Run read-only | Fixture output predates the current skill text. The fixture has no `SP-*` requirement and no story-to-story dependency |
| Pinned provenance | Checkout HEAD and the install SHA equal `upstream.commit`; the upstream ingestor's SHA-256 equals `upstream.json` | `git rev-parse`, `shasum`, `jq` | `upstream.json` says no plugin was installed, which Decision 0002 has since overtaken |
| Frontmatter validation by CLI | `claude plugin validate .claude --json` reports `success: true`, `manifest: null` and an empty `contents` | Run read-only | **May be vacuous**: needs the paired controls. `.claude` has no manifest, and a plugin-shaped directory with one is untried |
| Adapter under reduced environment | `claude --version` with only `PATH` in its environment exits 0 and prints `2.1.314 (Claude Code)`. Under `PATH=/usr/bin:/bin`, `command -v claude` exits 1 and `git` still resolves | Run read-only | A full harness run under that `PATH` was not tried, because it overwrites the report |

**Scenario "Keep development policy portable" is not met today.** `contracts.md`, `database.md`, `infrastructure.md`, `model-gateway.md`, `nextjs.md` and `python-worker.md` name a domain skill and link only to their owning source. None links to `scripts/verify.py`, `autobots-verify-change`, `autobots-review-change`, `autobots-reviewer` or a DH-W requirement. `delivery.md` links DH-W01-06. `ohmyorch-delivery.md` names its checks and the reviewer in prose but links only to Decision 0002. `AGENTS.md` has no Markdown links. Reading the common rules across assets found one real gap, the ingestor grammar above, and no contradictory copy. A reading does not prove absence, so implementation and review each repeat the comparison.

**Scenario "Separate optional assistant activation" has no implementation today.** `config_errors` never reads the `assistant` block, nothing compares a version with `minimum_version_for_blocking_hook_failure`, and no output says "inactive".

### What plugin activation means for the qualification values

`.claude/autobots.json` has two fields describing two adapters. Doctor's `project-config: schema 1 activated` and `enabled: true` mean bootstrap applied the plugin's project configuration under Decision 0002. That is neither of these fields, and it qualifies nothing.

| Field | Value | Describes | After this story |
|---|---|---|---|
| `upstream.delivery_plugin.event_delivery_qualification` | `not_qualified_one_pretooluse_event_observed` | The OhMyOrch plugin's hooks | Unchanged |
| `assistant.event_delivery_qualification` | `not_tested` | The project hooks in `.claude/settings.json` | Unchanged |

Neither becomes `inactive`: on this machine Claude Code 2.1.314 is present and above the 2.1.295 minimum, the plugin is enabled and hooks run, so `inactive` would be false as a stored value. Neither becomes qualified: no qualification exercise has been recorded, and the scenario forbids a new activation claim. Inactive is therefore a derived validation result, shown on arranged conditions. The two literals stay unchanged, by coordinator decision, and the evidence explains that they are not a complete list of observations.

### Decision 0001, cited by this story

The story cites Decision 0001's "Project decision" section. Decision 0002 supersedes only its clause against installing the plugin and importing its OpenSpec, archive and continuation machinery. The rest stands and applies here: the read-only ingestor, its paired writing skill, local path adaptation, and pinned provenance. The story text is not edited, and installing the plugin is not treated as a breach of this story. The ingestor adaptation stays independent of the plugin runtime, which `config_errors` already enforces. Decision 0001's refusal of upstream partial-pass completion also stands, narrowed only by the unmet-Given exception in Decision 0002. This story does not use that exception. That reading relies on the bridge rule's sentence marked "Coordinator's wording, not put to the user", as `implementation-plan.md` states under decision 2.

## Capabilities

### New Capabilities
- `development-assistant-assets`: portable shared instructions and project assets, an explicitly inactive optional adapter, and source-traceable ingestion that invents no product behavior.

### Modified Capabilities
None. `openspec list --specs` reports only `repository-prerequisite-inventory`, which this story does not change.

## Non-Goals

- Qualifying live assistant event delivery, or any claim that hooks, rules or the plugin are qualified.
- Checking the developer client's model route. Doing so would mean reading credentials or local settings that `AGENTS.md` puts out of bounds, so it is recorded as not checked.
- US-1.3 toolchains and scaffolding. US-1.4 runner and dispatcher work, including deadlines, check locks, dirty-domain marking and unsafe-input fixtures. US-1.5 templates and manifest validation. US-1.6 fault fixtures. US-1.7 disposable database and Compose guards. US-1.8 Gate 0 publication, including its adapter report.
- Implementing the pending `fast`, `full`, `db` or `operations` profiles. Rules link to them, and they keep failing explicitly.
- Rewriting the real `SPECS.md` through ingestion, or changing story text, statuses beyond the coordinator's routine edits, or any `SP-*`, `EPIC-*` or `US-*` identifier.
- Editing any PRD, Decision 0001, the pinned upstream checkout or prior evidence. `PRD-Development-Harness.md` writing `python3 scripts/verify.py` is reported as a source discrepancy, not changed.
- Any install, service or Docker start, database change, model provider or application model call. Changing developer-client model credentials.
- Reading or printing `.env` files, the provider master-key file, `.claude/settings.local.json` or environment dumps.

## Impact

- **Code and tests:** `scripts/harness_lib.py`, `scripts/verify.py`, new `tests/harness/test_assistant_assets.py`, new `tests/harness/forward_arrangement.py`. The harness report and printed summary gain one derived field; existing checks and `report_state` are unaffected.
- **Documents:** `docs/engineering/runbooks/development-harness.md`, `docs/engineering/ohmyorch-adaptation.md`.
- **Protected paths, through the bridge rule's procedure:** `./AGENTS.md`, `./CLAUDE.md`, `.claude/rules/contracts.md`, `.claude/rules/database.md`, `.claude/rules/infrastructure.md`, `.claude/rules/model-gateway.md`, `.claude/rules/nextjs.md`, `.claude/rules/python-worker.md`, `.claude/rules/ohmyorch-delivery.md`, `.claude/agents/autobots-spec-ingestor.md`, `.claude/skills/autobots-contracts/SKILL.md`, `.claude/skills/autobots-docker-local/SKILL.md`, `.claude/skills/autobots-durable-worker/SKILL.md`, `.claude/skills/autobots-implement-item/SKILL.md`, `.claude/skills/autobots-model-gateway/SKILL.md`, `.claude/skills/autobots-python/SKILL.md`, `.claude/skills/autobots-review-change/SKILL.md`.
- **Coordinator-owned:** `./SPECS.md`, `./CODEBASE.md`, `openspec/changes/us-1-2-h0-shared-instructions-development/`, `openspec/delivery/goal.md`, `docs/engineering/work-items/US-1.2.md`, `docs/engineering/evidence/US-1.2/`.
- **Coordinator edits already in the tree from US-1.1, reviewed here:** `.claude/rules/ohmyorch-delivery.md` and `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` (F-11, F-12 and two user rulings). They were uncommitted when this story was selected, by coordinator choice, while the bridge's start-of-goal check requires no other uncommitted work. They land in the US-1.2 commit, and the work item records this as a deviation.
- **Generated output:** only Git-ignored `.checks/` files and `__pycache__` bytecode. No new tool, so no new ignore rule, and `.gitignore` stays unchanged.
- **APIs, schema, dependencies, services:** none.

## Open Questions

None blocks implementation. The coordinator decided the planning questions, and `implementation-plan.md` lists each decision under Settled decisions. None was put to the user, none is a user ruling, and each stays open for the user to overturn. `SPECS.md` keeps `Open Questions: None` for this story, because `specs.py validate` rejects an unresolved question on an `IN PROGRESS` story, so the work item records the decisions and the final report repeats them.
