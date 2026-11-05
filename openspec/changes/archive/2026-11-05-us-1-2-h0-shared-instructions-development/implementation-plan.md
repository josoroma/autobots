# Implementation Plan — us-1-2-h0-shared-instructions-development

Story: US-1.2
Change: us-1-2-h0-shared-instructions-development

## Selected Story

US-1.2: H0 shared instructions and development assistant assets (EPIC-1, phase reference H0-02). Sources: SP-001, SP-017, DH-03, DH-04, Decision 0001's "Requested behavior" and "Project decision", SP-020. Dependency US-1.1 is `DONE`.

Acceptance, quoted from `./SPECS.md`:

```gherkin
Scenario: Keep development policy portable
  Given shared engineering standards and the approved local/OpenRouter boundary
  When AGENTS.md, CLAUDE.md and project rules, skills, agents and settings are authored
  Then common rules are not duplicated inconsistently and each rule links to a check or review responsibility

Scenario: Separate optional assistant activation
  Given an unavailable or incompatible Claude adapter
  When its configuration is validated
  Then it remains explicitly inactive and no new model provider, paid review call or activation claim is introduced

Scenario: Ingest without inventing product behavior
  Given approved PRDs, preserved SP requirements and descriptive CODEBASE context
  When the read-only adapted ingestor returns a proposed backlog and its paired caller persists it
  Then stories cite their sources, contain Given/When/Then acceptance, preserve stable identities and honest dependencies/statuses, and generate navigation without implementing product code or claiming delivery complete
```

The assets mostly exist, so this change closes observed gaps and re-verifies the rest. See `proposal.md` for what is already present and the evidence for it. Decision 0002 supersedes only the plugin and machinery clause of the cited Decision 0001; the story text stays as written.

**Bridge rule requirements carried here, since specialists may not see it.** The plan names every protected path. The implementer returns protected content under a heading naming the path; the coordinator writes it verbatim before capture; the reviewer checks it as implementation. Capture runs immediately before every review. Verdicts state `Reviewed fingerprint: <hex>` on its own line, never on the `Verdict:` or `Blocking:` line or in a criterion row.

### Settled decisions: the coordinator's, not the user's

The architect's critique marked these as needing a user decision. The coordinator decided all seven on 2026-11-04 so that planning could proceed. None was put to the user and none is a user ruling; the relayed user request does not address any of them. "Settled" means only that this plan proceeds on them. Each stays open for the user to overturn. The work item records all seven, and the final report repeats them in those terms, because `SPECS.md` keeps `Open Questions: None` (`specs.py validate` rejects an unresolved question on an `IN PROGRESS` story). They interpret acceptance, and none changes its text.

1. **"Each rule" granularity.** One link per `.claude/rules` file, and one mapping row per rule-bearing `AGENTS.md` section, including Completion evidence and the Commands profile statement. Skills and agents are covered by a per-file DH-04 table instead of per-rule links.
2. **Scenario "Separate optional assistant activation". Confirmed by the user on 2026-11-05, so no longer the coordinator's:** the story implements this behavior, and a process-scoped `PATH` and a stub arrange its Given, so it is scored from observation: `PASS` only if observed, stating plainly that the condition was arranged and no real adapter was inactive on this machine. The unmet-Given exception does not apply.
3. **"Incompatible"** means presence, version and configuration validity. The developer client's model route is recorded as not checked, because checking would mean reading credentials or local settings that `AGENTS.md` puts out of bounds.
4. **`claude plugin validate`.** Task 2.6's control tries the `.claude` shape and a plugin-shaped directory with a manifest under `--strict`. If neither pair discriminates, the task closes on harness frontmatter checks. That fallback does not meet DH-04's "validate frontmatter against the qualified CLI" clause, so the clause is reported as not met, as an open limitation in the adaptation page, the evidence and the final report, and never as met. The nearest basis is US-1.2#2 ("record pinned provenance, syntax and optional adapter limitations") and H0.2 ("Files validate against documented syntax"). The tension stays visible: DH-09.1 says a required behavior that depends on an unavailable check leaves the item incomplete or blocked, and the bridge's Stopping section covers decisions the sources do not make. Closing with the limitation is the coordinator's reading, and if the user rejects it the story blocks.
5. **Forward exercise.** The coordinator is the ingestor's paired caller: it delegates the read-only `autobots-spec-ingestor` and persists the output verbatim to the disposable copy, following the paired skill's steps with the root substitution written in the runbook, recording hashes of the ingestor and skill. The tester runs `render` and `validate` itself and does all scoring.
6. **Qualification literals.** The two `event_delivery_qualification` values stay unchanged, and the evidence explains that they are not a complete list of observations.
7. **Carried edits.** The edits to the bridge rule and Decision 0002 were uncommitted at `select` by coordinator choice, and the work item says so as a deviation from the bridge's start-of-goal check, because they land in the US-1.2 commit.
8. **Records row (reopen round 1, review F-3).** `docs/engineering/option-b-contract.md` line 70 makes a runbook's last-exercised revision, date and result mandatory for a verified claim, and SP-018 leans toward the runbook recording them. The coordinator's reading: the runbook is final at capture and links to the story's evidence, which must state them. This is not a user ruling. If the evidence summary does not state them and list untested steps, the common-rules table's last row reads `no`.

## OpenSpec Artifacts

- `openspec/changes/us-1-2-h0-shared-instructions-development/proposal.md`: scope, non-goals, observed state, what plugin activation means for the qualification values, and the treatment of Decision 0001.
- `openspec/changes/us-1-2-h0-shared-instructions-development/specs/development-assistant-assets/spec.md`: three requirements, each carrying one of the story's scenarios.
- `openspec/changes/us-1-2-h0-shared-instructions-development/design.md`: rule-link form, derived adapter status, activation refusal, forward exercise, DH-04 inspection, syntax control.
- `openspec/changes/us-1-2-h0-shared-instructions-development/tasks.md`: fourteen tasks under the story's two task groups.

Base revision is `9714930`. `openspec validate --strict` and `validate-implementation-plan` both exited 0 on the previous persisted version of these artifacts when the Planner reran them on 2026-11-04. This revision has not been run through either, because the Planner writes nothing; the Planner read the plan validator and kept the required sections, and the spec delta is unchanged. The coordinator should run `openspec validate us-1-2-h0-shared-instructions-development --strict` and the plan validator after persisting them.

## Implementation Order

**Coordinator, first:** persist these artifacts, then open `docs/engineering/work-items/US-1.2.md` with the plan, the seven decisions stated as the coordinator's, Decision 2's reliance on the unconfirmed bridge sentence, and the carried-edit deviation.

**Implementer, first pass (code and authoring):**

1. Record the starting state: `git status --short > .checks/US-1.2/status-before.txt` and `shasum -a 256 SPECS.md > .checks/US-1.2/specs-before.sha256`.
2. Tasks 2.1 and 2.2: adapter status and activation refusal, with tests. Everything else can be tested independently of these.
3. Task 2.6: the CLI syntax control, including the plugin-shaped pair, because task 2.4's page must state its result. It needs nothing else.
4. Tasks 1.1, 1.2 and 1.6: the static checks, tests and arrangement script. The rule-link test, the `AGENTS.md` mapping test and `project_configuration` are expected to fail on the real tree until the protected content lands, and the adapter then reads `configuration_invalid`. Report this; do not tick 1.1.
5. Task 1.7 and the first run of task 1.4: inspect skills and agents against DH-04 and compare the common rules. Both come before any authoring. A needed change to a protected path this plan does not name stops here for a plan amendment. Do not tick 1.4 yet, because its "Story field order" row reads `no` until task 1.5 lands.
6. Tasks 1.3, 1.8 and 1.5: author protected content. Pre-test it by copying the affected files to a scratch root under `.checks/US-1.2/` and running the new checks against that root. Return each file under a heading naming its path, with what could not be tested.

**Coordinator:** write each returned file verbatim with the Edit tool and record which paths went through this procedure in the Implementation section. A needed change goes back to the implementer. The harness stays red between these passes, so a Stop-hook block here is expected.

**Implementer, second pass:**

7. Run the checks against the real files and tick 1.1, 1.3, 1.5 and 1.8 only if they pass.
8. Tasks 2.3 and 2.4: runbook and adaptation page. Both must be final here.
9. Re-run task 1.4 on the final tree, and repeat task 1.7's row for each edited file. This follows step 8 rather than step 7, because the runbook and adaptation page are among the compared copies and change in step 8. Return both final tables. Tick 1.4 only if every row reads `yes`. A needed protected change goes back through the coordinator, and this step then repeats.
10. Task 2.5.

**Coordinator, before review:** write the Implementation section. Persist the implementer's final tables verbatim to `docs/engineering/evidence/US-1.2/dh-04-table.md` and `docs/engineering/evidence/US-1.2/common-rules-table.md`. Then run the bridge rule's capture commands. `is_record` in `scripts/story_manifest.py` excludes these tables from the manifest, so they reach the reviewer only as separately handed paths.

**Review, then forward exercise, then test:**

11. Reviewer: covers implementation, protected paths, the two persisted tables and the coordinator's US-1.1 edits. See Review Scope below.
12. Coordinator, as the ingestor's paired caller, after review passes and before delegating the tester: arrange and run the forward exercise per the runbook, with all output under `.checks/US-1.2/forward/`. On a reopen, repeat it under a new directory, because the arrangement script refuses an existing destination.
13. Tester: runs `render` and `validate` on the forward copy, scores all three scenarios and exercises the runbook.

## Task to Acceptance Mapping

| Task | Acceptance criterion | Notes |
|---|---|---|
| 1.1 Rule-link and `AGENTS.md` mapping checks | Scenario: Keep development policy portable | Makes "each rule links" enforced |
| 1.2 Link, frontmatter, path and shared-fact tests | Scenario: Keep development policy portable | Representative paths come from DH-03, a cited source. Shared-fact tests serve "not duplicated inconsistently" for what can be measured |
| 1.3 Protected rule, `AGENTS.md` and `CLAUDE.md` content | Scenario: Keep development policy portable | Closes the observed gap |
| 1.4 Common-rule comparison | Scenario: Keep development policy portable | Inspection, because contradiction in prose is not mechanically decidable. Run before authoring and again on the final tree |
| 1.5 Ingestor `Change:` grammar | Scenario: Ingest without inventing product behavior | Serves "preserve stable identities and honest dependencies/statuses" on a story in progress |
| 1.6 Read-only role, pairing, fixture and arrangement tests | Scenario: Ingest without inventing product behavior | Static and fixture regression; does not replace the forward exercise |
| 1.7 DH-04 per-file table | Scenario: Keep development policy portable | The coverage for skills and agents under decision 1 |
| 1.8 Protected skill content | Scenario: Keep development policy portable | Closes gaps the table finds |
| 2.1 Derived adapter status | Scenario: Separate optional assistant activation | Implements "explicitly inactive" |
| 2.2 Activation and provider refusal | Scenario: Separate optional assistant activation | Implements "no new model provider, paid review call or activation claim" and an invalid configuration reading inactive |
| 2.3 Runbook | Scenario: Separate optional assistant activation; Scenario: Ingest without inventing product behavior | DH-W05 |
| 2.4 Provenance and limits record | Scenario: Keep development policy portable; Scenario: Separate optional assistant activation; Scenario: Ingest without inventing product behavior | Story task US-1.2#2 |
| 2.5 Backlog and harness checks | Scenario: Keep development policy portable; Scenario: Separate optional assistant activation; Scenario: Ingest without inventing product behavior | Harness evidence only |
| 2.6 CLI syntax control | Scenario: Keep development policy portable | H0.2's documented syntax for authored assets; story task US-1.2#2 |

Mapped: 14 of 14. The coordinator's edits from US-1.1 to the bridge rule and Decision 0002 are already in the tree and carry no task. They change no acceptance behavior, and the reviewer covers them.

## Affected Files

Likely scope, from reading each file and the write-scope script (`scripts/check-write-scope.sh` in the plugin blocks the implementer for the protected rows).

| Path | Expected change | Evidence |
|---|---|---|
| `scripts/harness_lib.py` | Rule-link check, `AGENTS.md` mapping check, adapter status, activation refusal, all reached from or beside `config_errors` | Read: `config_errors` ignores the `assistant` block and rule links. Existing tests call it on partial fixtures and assert only `any` or a filtered count, so new errors do not break them |
| `scripts/verify.py` | One derived `assistant_adapter` report field, and its state and reason in the printed summary | Read: report construction and summary. `report_state` requires three checks, so no new check. `git grep` finds no consumer of the stdout in `.claude/hooks/dispatch.py` |
| `tests/harness/test_assistant_assets.py` | New test module | `tests/harness/test_hooks.py` and `tests/harness/test_specs.py` read; no test covers rule links, frontmatter keys, tool sets or adapter status |
| `tests/harness/forward_arrangement.py` | New arrangement script. Not matched by the harness's `test_*.py` discovery | Design D5; `scripts/verify.py` discovery pattern read |
| `docs/engineering/runbooks/development-harness.md` | Adapter status, its coverage, recovery rows, forward procedure, and the existing "Evidence and last exercise" section replaced by a link to US-1.2 evidence | Read: sections "Inspect or use the assistant integration" and "Evidence and last exercise". `git grep` finds no link to that section's fragment |
| `docs/engineering/ohmyorch-adaptation.md` | Validation record section, including the observed syntax result | Read: it is the existing provenance page |
| `./AGENTS.md` | **Protected.** One section mapping each rule-bearing section, `.claude/settings.json` and `CLAUDE.md` to a check and review responsibility | Read: no Markdown links |
| `./CLAUDE.md` | **Protected.** Runbook link, outside the `OHMYORCH` managed block | Read: "documented runbook" has no link |
| `.claude/agents/autobots-architect.md` | **Protected, reopen round 1 (review F-1).** One clause in the Return sentence naming invariants checked and source evidence | DH-04 result contract; reviewer rejected the `yes` cell |
| `.claude/agents/autobots-nextjs.md` | **Protected, reopen round 1 (review F-1).** One clause in the Return sentence naming invariants checked | DH-04 result contract; reviewer rejected the `yes` cell |
| `.claude/rules/contracts.md` | **Protected.** Check and review section | Link scan: no check or review target |
| `.claude/rules/database.md` | **Protected.** Same | Same |
| `.claude/rules/infrastructure.md` | **Protected.** Same | Same |
| `.claude/rules/model-gateway.md` | **Protected.** Same | Same |
| `.claude/rules/nextjs.md` | **Protected.** Same | Same |
| `.claude/rules/python-worker.md` | **Protected.** Same | Same |
| `.claude/rules/ohmyorch-delivery.md` | **Protected.** One added line of links, on top of the coordinator's existing F-12 edit | Link scan; `git diff` shows the existing edit |
| `.claude/agents/autobots-spec-ingestor.md` | **Protected.** `Change:` line added to the story grammar, and its preservation | Read: its field order omits the line that `scripts/specs.py` accepts and `./SPECS.md` uses |
| `.claude/skills/autobots-contracts/SKILL.md` | **Protected.** Likely relevant-paths line, from `.claude/rules/contracts.md` | DH-04 table below |
| `.claude/skills/autobots-docker-local/SKILL.md` | **Protected.** Likely relevant-paths line, from `.claude/rules/infrastructure.md`, and failure-behavior line | DH-04 table below |
| `.claude/skills/autobots-durable-worker/SKILL.md` | **Protected.** Likely relevant-paths line, from `.claude/rules/python-worker.md`, and failure-behavior line | DH-04 table below |
| `.claude/skills/autobots-implement-item/SKILL.md` | **Protected.** Likely relevant-paths line, from DH-03's work-item, evidence and runbook paths, since no rule matches this skill | DH-04 table below |
| `.claude/skills/autobots-model-gateway/SKILL.md` | **Protected.** Likely relevant-paths line, from `.claude/rules/model-gateway.md`, and failure-behavior line | DH-04 table below |
| `.claude/skills/autobots-python/SKILL.md` | **Protected.** Likely failure-behavior line | DH-04 table below |
| `.claude/skills/autobots-review-change/SKILL.md` | **Protected.** Likely relevant-paths line, from DH-03's work-item, evidence and runbook paths, since no rule matches this skill | DH-04 table below |
| `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` | Coordinator edit already in the tree (F-11, two rulings). No further change expected | `git diff` |
| `./SPECS.md` | Coordinator-owned status and task edits | Already edited at `select`; ticked at `mark-done` per the bridge rule |
| `./CODEBASE.md` | Coordinator-owned; revision already refreshed. Likely refreshed again at the next `select` | `git diff`; bridge rule |
| `openspec/changes/us-1-2-h0-shared-instructions-development/` | Implementer ticks `tasks.md`; coordinator owns planning files and `status.md`; reviewer and tester add verdicts | Directory listing; write-scope script |
| `openspec/delivery/goal.md` | Coordinator-owned derived state | Already modified |
| `openspec/specs/development-assistant-assets/spec.md` | Created by `archive`, as US-1.1's archive did for its capability | `git show --stat 9714930` |
| `docs/engineering/work-items/US-1.2.md` | Coordinator-owned DH-W record | Bridge rule, Records section |
| `docs/engineering/evidence/US-1.2/` | Coordinator-owned `dh-04-table.md` and `common-rules-table.md` before capture; `reviewed-manifest.json` from capture; later the summary and manifests and the retained forward-run copy | Bridge rule; `is_record()` in `scripts/story_manifest.py` excludes this directory from the manifest |

**Expected unchanged,** each covered by the `git diff --quiet` block under "Scenario: Separate optional assistant activation":

- `.claude/settings.json`, `.claude/autobots.json`, `.claude/hooks/dispatch.py`
- `.claude/rules/delivery.md`, which already links DH-W01-06
- `./.gitignore`
- `.claude/skills/autobots-nextjs/SKILL.md`, `.claude/skills/autobots-plan-change/SKILL.md`, `.claude/skills/autobots-runbook-evidence/SKILL.md`, `.claude/skills/autobots-spec-ingest/SKILL.md`, `.claude/skills/autobots-supabase/SKILL.md`, `.claude/skills/autobots-verify-change/SKILL.md`
- `.claude/agents/autobots-database.md`, `.claude/agents/autobots-infrastructure.md`, `.claude/agents/autobots-python-worker.md`, `.claude/agents/autobots-reviewer.md`

Naming them here makes `check-scope` treat them as predicted, which is why that block has to cover them. Naming them does not authorize changing them. A needed change to one is a plan amendment first, and the amendment takes the path out of the block and, for the ingest skill, moves its binding row to the manifest comparison.

**Runbook path:** `docs/engineering/runbooks/development-harness.md` (above). No new runbook.

**Generated output.** All Git-ignored, so none should affect `compare`, and this story introduces no tool that needs a new ignore rule:

- `.checks/harness/latest.json` and its lock, from `scripts/verify.py`.
- `.checks/US-1.2/` scratch files, stubs, the validate control including its scratch `.claude-plugin/plugin.json` manifests, the forward run and `changed.txt`.
- Bytecode under the existing ignored `__pycache__` directories.

A retained copy of the forward run goes under `docs/engineering/evidence/US-1.2/forward-fixture/` as a record, which `compare` excludes.

### DH-04 table: Planner's reading, which task 1.7 repeats

This is a reading, not a result. A gap means the file does not state the element in terms a reader can act on.

| Skill | Trigger | Relevant paths | Prerequisites | Workflow | Expected evidence | Failure behavior |
|---|---|---|---|---|---|---|
| `autobots-contracts` | yes | **gap** | yes | yes | yes | yes |
| `autobots-docker-local` | yes | **gap** | yes | yes | yes | **gap** |
| `autobots-durable-worker` | yes | **gap** | yes | yes | yes | **gap** |
| `autobots-implement-item` | yes | **gap** | yes | yes | yes | yes |
| `autobots-model-gateway` | yes | **gap** | yes | yes | yes | **gap** |
| `autobots-nextjs` | yes | yes | yes | yes | yes | yes |
| `autobots-plan-change` | yes | yes | yes | yes | yes | yes |
| `autobots-python` | yes | yes | yes | yes | yes | **gap** |
| `autobots-review-change` | yes | **gap** | yes | yes | yes | yes |
| `autobots-runbook-evidence` | yes | yes | yes | yes | yes | yes |
| `autobots-spec-ingest` | yes | yes | yes | yes | yes | yes |
| `autobots-supabase` | yes | yes | yes | yes | yes | yes |
| `autobots-verify-change` | yes | yes | yes | yes | yes | yes |

| Agent | Scope | Permitted tools | Inputs | Result contract |
|---|---|---|---|---|
| `autobots-architect` | yes | yes, read-only | yes | yes |
| `autobots-database` | yes | yes | yes | yes |
| `autobots-infrastructure` | yes | yes | yes | yes |
| `autobots-nextjs` | yes | yes | yes | yes |
| `autobots-python-worker` | yes | yes | yes | yes |
| `autobots-reviewer` | yes | yes, read-only | yes | yes |
| `autobots-spec-ingestor` | yes | yes, read-only | yes | yes |

DH-04's result contract names "invariants checked" and "remaining uncertainty". The agents state these in varying words; task 1.7 judges each. All 13 skills link to detailed standards. No skill applies a persistent operation, so none needs `disable-model-invocation` yet, by reading.

## Test Strategy

Evidence classes are DH-09.2's: `static`, `mock`, `disposable`, `live`. Application model transport is `none` throughout. `live` below means only the real local CLI's version output, and qualifies nothing. The harness report's existing `static_or_fixture` label is outside DH-09.2 and belongs to US-1.4; the evidence summary maps it to `disposable`, since those tests build temporary fixtures. The harness profile is harness evidence only, and none of this establishes H0, H1 or product acceptance.

### Probe rules for the Implementer and Tester

The project hook denies any Bash command naming the provider master-key file, any `cat`, `head`, `tail`, `less` or `more` of a `.env` path, a Supabase database reset, Docker system or volume prune, Docker down with volume removal, and commands over 20,000 characters. The Read tool is denied on secret files. To stay clear of it:

- Write the master-key file in prose only. Do not name, locate, open or test it, and do not search `PRD-Model-Providers.md` for it.
- Search with `git grep`, which skips ignored files, or name specific files. A recursive `grep` over the tree reaches `.claude/settings.local.json`.
- Never copy the repository's `.claude/` as a whole, including to a scratch root, because that copies `.claude/settings.local.json`. Copy only `skills/`, `agents/`, `rules/`, `settings.json` and `autobots.json` by name. The retained fixture's own `.claude/` holds only `autobots.json`, so copying that fixture is not covered by this rule.
- If a probe is denied, leave it out and report it. Do not rephrase, encode or split it.

Also never run: `env`, `printenv` or anything printing `PATH`; any `supabase` command, including `supabase --version`, which appears to make an outbound check and is not needed here; any `docker` command; `claude -p` or any Claude prompt; any install or service start. The only Claude CLI uses are `claude --version` and `claude plugin validate`, with or without `--strict`. Read `~/.claude/plugins/installed_plugins.json` only through a `jq` filter on this plugin's entry.

Setting `PATH` for one process is fine, but never echo it. Use `python3.12` or `/opt/homebrew/bin/python3.12`, since `python3` is an alias in zsh. Set `PYTHONDONTWRITEBYTECODE=1` on direct test runs. Use a new scratch subdirectory per run rather than `rm -rf` on a variable path. Run the normal `verify.py` last, because arranged runs overwrite `.checks/harness/latest.json`.

### Scenario: Keep development policy portable

The Given holds on the real repository: `AGENTS.md` and the mapped sources state the standards and the boundary. The exception does not apply.

| Check | Command or method | Expected | Class |
|---|---|---|---|
| Tests | `PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/harness -p 'test_assistant_assets.py' -v` | Exit 0; nonzero test count; each negative fixture fails as asserted, including a rule linked only to a non-DH-W PRD anchor and a new `AGENTS.md` heading with no row. The mapping section's own heading needs no row | `disposable` |
| Rule links | Inspection of each rule file's section | Link is apt for that layer and profile (DH-09) | `static` |
| `AGENTS.md` mapping | `project_configuration` fails when it is removed, by the tests above; then inspection | One row per rule-bearing section, including Completion evidence and Commands, and each row's responsibility is apt | `static` |
| Settings and `CLAUDE.md` responsibility | Inspection of the mapping table | `.claude/settings.json` names `project_configuration` and `autobots-review-change`. The `CLAUDE.md` row says the check covers the hook configuration its hook sentence describes, not the sentence, because `config_errors` never reads `CLAUDE.md` | `static` |
| Skills and agents | Reviewer repeats the table in `docs/engineering/evidence/US-1.2/dh-04-table.md`, reading each file | One row per file; no unresolved gap. Only the tool-set test is mechanical | `static` |
| Common rules | Inspection against the table below, starting from `docs/engineering/evidence/US-1.2/common-rules-table.md` | Every row of the final-tree run reads yes: no contradiction among authored assets. `PRD-Development-Harness.md`'s `python3` is a reported source discrepancy, not a passing row. A contradiction in an unnamed protected path needs a plan amendment or a delivery block, never a listing | `static` |
| Pending profiles | The tests read `verification.pending_profiles`; also run `python3.12 scripts/verify.py --profile <p>` for each listed profile | Each exits 2 with `not_implemented`, so rules link to explicit failures rather than to passes | `static` |
| Syntax, CLI | Result of task 2.6's two pairs under `.checks/US-1.2/validate-control/`; rerun on the final tree's copies | A pair counts only if its good copy passes and its broken copy's error names the frontmatter fault. If neither counts, decision 4 applies: DH-04's "qualified CLI" clause is reported as not met, in the page and the evidence | `disposable` |
| Syntax, harness | The frontmatter-key test | Only allowlisted keys; agent `model` is `inherit` | `static` |
| Managed block | `git diff HEAD -- CLAUDE.md` and plugin doctor | Only lines outside the `OHMYORCH` block; no failing doctor check | `static` |
| Harness | `python3.12 scripts/verify.py --profile harness` | Exit 0 | `static` for `project_configuration`, `disposable` for tests |

A test of link presence does not show the responsibility is real. The profiles a rule links to are unimplemented, so those links name a future check, and the review responsibility is what applies today. Whether project rules actually load in a live session is not established here.

**Common rules to compare (task 1.4, and the reviewer repeats it).** Results below are the Planner's reading only. Task 1.4 answers yes or no for every row, including the review-independence row, and does not leave any row to the reviewer. It runs before authoring and again on the final tree, and the persisted table is the final-tree run.

| Common rule | Copies | Planner's reading |
|---|---|---|
| Profile availability | `./AGENTS.md`, `.claude/rules/delivery.md`, `.claude/skills/autobots-verify-change/SKILL.md`, `.claude/autobots.json`, `scripts/verify.py`, `docs/engineering/runbooks/development-harness.md`, `./README.md` | Yes |
| Interpreter | `./AGENTS.md`, `.claude/settings.json`, `.claude/autobots.json`, the runbook | Yes. `PRD-Development-Harness.md` says `python3`; it is a source, not an authored asset, and is not edited. Report it as a source discrepancy |
| OpenRouter-only and no new provider | `./AGENTS.md`, `.claude/rules/model-gateway.md`, `.claude/skills/autobots-model-gateway/SKILL.md`, `./CLAUDE.md` | Yes |
| No automatic actions in hooks | `./AGENTS.md`, `.claude/rules/delivery.md`, `.claude/skills/autobots-docker-local/SKILL.md`, `.claude/hooks/dispatch.py` | Yes |
| Review independence and record ownership | `./AGENTS.md`, `.claude/rules/delivery.md`, `.claude/rules/ohmyorch-delivery.md`, `.claude/skills/autobots-review-change/SKILL.md`, `.claude/agents/autobots-reviewer.md`, the `./CLAUDE.md` managed block, `.claude/skills/autobots-implement-item/SKILL.md`, `.claude/skills/autobots-plan-change/SKILL.md` | Yes. `ohmyorch:reviewer` writes a verdict and `autobots-reviewer` returns findings: two named roles, and no file says one role both may and may not write. Decision 0002 draws the distinction. Task 1.4 tests this question and answers it |
| Document map | `.claude/autobots.json`, `.claude/ohmyorch/project.json` | Yes; task 1.2 tests it |
| Upstream pin | `.claude/autobots.json`, `.claude/skills/autobots-spec-ingest/SKILL.md`, `.claude/agents/autobots-spec-ingestor.md`, `docs/engineering/ohmyorch-adaptation.md`, `./CODEBASE.md` | Yes; task 1.2 tests the first three |
| Plugin stance | Decisions 0001 and 0002, the adaptation page, `./CLAUDE.md`, the ingest skill | Yes, given 0002's supersession note and the page's banner. `CLAUDE.md`'s sentence is about what hooks do |
| Ingestion ownership | `./CLAUDE.md`, `.claude/skills/autobots-spec-ingest/SKILL.md`, `.claude/agents/autobots-spec-ingestor.md`, the runbook | Yes. The coordinator is the caller. The exercise's split of `render` and `validate` is stated in the runbook as specific to the exercise |
| Story field order | `.claude/agents/autobots-spec-ingestor.md`, `scripts/specs.py` | **No, today:** the ingestor omits `Change:`. Task 1.5 fixes it through a named path, and the final-tree run must read yes |
| Evidence locations | `./AGENTS.md`, `.claude/rules/delivery.md`, the verify and runbook-evidence skills, DH-09.2 | Yes |

Some copies are in protected paths this plan does not authorize changing: the expected-unchanged paths above and `./README.md`. A contradiction found there stops for a plan amendment naming the path, or a delivery block.

### Scenario: Separate optional assistant activation

**This Given does not hold on the real machine:** Claude Code 2.1.314 is present and above the 2.1.295 minimum. Under decision 2, which rests on the coordinator's unconfirmed bridge sentence, it is arranged, and the unmet-Given exception does not apply. "Unavailable or incompatible" holds if either is arranged, and both are. The Tester scores `PASS` only from what it observes, and the report must say the result covers arranged conditions and that no real adapter was inactive on this machine.

`assistant_adapter` is the likely field name. The runbook carries the final one.

| Check | Command or method | Expected | Class |
|---|---|---|---|
| Given, unavailable | `PATH=/usr/bin:/bin /bin/sh -c 'command -v claude'` | Non-zero exit. The Planner observed exit 1, and that `git` still resolves there | `disposable` |
| Validate, unavailable | `PATH=/usr/bin:/bin /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness`, then `jq '.status, .assistant_adapter, .not_tested' .checks/harness/latest.json` | Exit 0; `passed`; state `inactive`, reason `unavailable`; `model_route` `not_checked`; `not_tested` still lists Claude event delivery; the printed summary also shows state and reason | `disposable` |
| Validate, incompatible | Same, with `PATH` starting at the absolute path of `.checks/US-1.2/stub/`, where a stub `claude` prints `2.1.200 (Claude Code)` and appends its arguments to a file | Exit 0; state `inactive`, reason `version_below_minimum`; the stub's record holds only `--version` | `mock` |
| Failure modes and call surface | The adapter tests in `tests/harness/test_assistant_assets.py` | Failing, hanging and unparsable versions give `inactive`, and the hanging case returns promptly. 2.1.99 is below and 2.1.1000 above the minimum, which string comparison gets wrong. 2.1.295 is `configured_unqualified`. Each state is compared as a whole value against `inactive` and `configured_unqualified`, because `inactive` contains "active" and `configured_unqualified` contains "qualified", so a substring test could not fail correctly. The stub records that only `--version` ran | `mock` |
| Invalid configuration | The same module, with a stub compatible version | Each negative configuration gives `inactive`, reason `configuration_invalid` or `minimum_unknown`, not only an error | `disposable` |
| Refusal | The same module's negative fixtures | `not_tested_but_active`, `prompt` or `agent` hooks, and `model`, `env` or `permissions` keys all produce errors | `disposable` |
| Real state, not scored as the Given | `python3.12 scripts/verify.py --profile harness`, then the same `jq` | Exit 0; state equals `configured_unqualified` and reason equals `delivery_unverified` | `live` |
| Nothing newly claimed, and every expected-unchanged path | The `git diff --quiet` block below | Exit 0 | `static` |
| No provider added, no paid review call | The scan below, over added lines in scripts, hooks and tests and over the two new files; plus the test that agent `model` is `inherit` and the stub record above | No hit, or each hit inspected and explained, such as a negative-fixture string | `static` |
| No activation wording | Inspection of changed instruction, runbook and adaptation text | Nothing reads as hooks, plugin or adapter being qualified or event delivery proven | `static` |
| Values | `jq '.assistant, .upstream.delivery_plugin' .claude/autobots.json` | `not_tested` and `not_qualified_one_pretooluse_event_observed`, unchanged | `static` |

```sh
git diff --quiet HEAD -- \
  .claude/settings.json .claude/autobots.json .claude/hooks/dispatch.py \
  .claude/rules/delivery.md .gitignore \
  .claude/skills/autobots-nextjs/SKILL.md .claude/skills/autobots-plan-change/SKILL.md \
  .claude/skills/autobots-runbook-evidence/SKILL.md .claude/skills/autobots-spec-ingest/SKILL.md \
  .claude/skills/autobots-supabase/SKILL.md .claude/skills/autobots-verify-change/SKILL.md \
  .claude/agents/autobots-database.md \
  .claude/agents/autobots-infrastructure.md \
  .claude/agents/autobots-python-worker.md .claude/agents/autobots-reviewer.md
```

```sh
git diff HEAD -- scripts .claude/hooks tests/harness | grep -E '^\+' | grep -inE 'anthropic|ollama|litellm|openai|bedrock|vertex|gemini|claude[[:space:]]+(-p|--print)|--print\b'
grep -inE 'anthropic|ollama|litellm|openai|bedrock|vertex|gemini|claude[[:space:]]+(-p|--print)|--print\b' tests/harness/test_assistant_assets.py tests/harness/forward_arrangement.py
```

Baseline: `git grep` finds none of the provider names in `scripts`, `.claude/hooks` or `tests/harness` today.

Fixture runs do not show how a real unavailable client behaves or prove anything about event delivery. Only the project file is validated, not effective settings across scopes. The field does not separate project hooks from plugin hooks. The developer client's model route is not checked, under decision 3, so `configured_unqualified` must not be read as compatible. The evidence and report say all of this.

### Scenario: Ingest without inventing product behavior

The Given is arranged on a synthetic fixture, and the first row below checks that it was. `PRD.md` stands in for approved PRDs, `CONTRACT.md`'s synthetic `SP-*` sections for preserved SP requirements, and `CODEBASE.md` for descriptive context. No claim is made about the real PRDs. The ingestor file changes in this story, and the current skill's hash (`96ed8ed…`) differs from the one in HARNESS-ADAPT-001's manifest (`c62463a…`), so the retained fixture alone cannot show current behavior. Its Product Context also records that it has no `SP-*` identifiers, and no story depends on another, so it cannot exercise those clauses.

**Arrangement, by `tests/harness/forward_arrangement.py`, fixed before the run.** It takes its destination as its one argument. It copies `docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture/` and its hidden `.claude/autobots.json`, then applies:

- New `AGENTS.md`, one line: `This synthetic fixture's backlog stories cite their sources and claim no delivery.`
- Appended to `CONTRACT.md`:

```markdown
## SP-901 Missing-key draft preservation
The backlog must retain a story covering REQ-01.

## SP-902 Retry visibility
The backlog must retain a story covering REQ-03.
```

- Appended to `PRD.md`:

```markdown
## REQ-06 Composer autosave
When the composer draft changes, save the current draft automatically using the local storage required by REQ-02. This behavior cannot be delivered until local storage is delivered.
```

- In `SPECS.md`: the Product Context sentences saying there are no `SP-*` identifiers and no `AGENTS.md` are replaced by `The supplied sources define SP-901 and SP-902 and no H0/H1/B phase definitions. The dependency of US-1.3 on US-1.2 is part of this existing backlog.` A `**Preserved SP coverage**` table is added with rows SP-901 to US-1.1 and SP-902 to US-1.3, in the shape of the real `SPECS.md`. US-1.1 and US-1.3 gain a `Source:` item citing their SP section. US-1.2 becomes `Status: IN PROGRESS` with `` Change: `openspec/changes/fixture-us-1-2/` `` directly below it. US-1.3's dependencies become `- US-1.2`. Navigation is rendered.

**Expected result, fixed before the run:** US-1.1 stays `READY`, US-1.2 stays `IN PROGRESS` with its `Change:` line, US-1.3 stays `NEEDS CLARIFICATION` with its dependency, and US-1.4 stays `BLOCKED`. One new story takes the next free ID, US-1.5, in EPIC-1. It cites `PRD.md#req-06-composer-autosave`, has `Dependencies: - US-1.2` and `Status: BLOCKED`, because REQ-06 states its trigger and US-1.2 is not `DONE`. Any other result, including `NEEDS CLARIFICATION` on the new story, is a finding, and nobody repairs the copy to match.

**Exercise, by the coordinator as paired caller, under decision 5.** The runbook writes these as the skill's steps. `F` names one run's directory and every run uses a new one, because the arrangement script refuses an existing destination. Shell variables do not carry between separate Bash tool calls, so set them at the start of each call, and run from the repository root in bash or zsh. Process substitution is not available in `/bin/sh`.

1. Run the block below. Skill step 1: read `SPECS.md` and `CODEBASE.md` under `$F/run-1`. The copy's map has no `design` key, which is recorded as a gap and changes nothing.

   ```sh
   F=.checks/US-1.2/forward
   python3.12 tests/harness/forward_arrangement.py "$F/run-1"
   cp -R "$F/run-1" "$F/before"
   ```

2. Record the definitions on disk, as below. Skill step 2: delegate `autobots-spec-ingestor` with the absolute path of `$F/run-1` as project root, the resolved paths, explicit decisions (none), existing identifiers, and a bounded scope: add stories for requirements with no story, and preserve the rest. This uses the developer assistant like every other specialist in the loop, and is not application inference.

   ```sh
   F=.checks/US-1.2/forward
   shasum -a 256 .claude/agents/autobots-spec-ingestor.md .claude/skills/autobots-spec-ingest/SKILL.md > "$F/delegation.sha256"
   ```

3. Skill step 3: inspect the output and record what was seen. No edits; a discrepancy is a finding.
4. Skill step 4: persist the returned document verbatim to `$F/run-1/SPECS.md`. Keep `INGESTION SUMMARY` and the raw response as separate files, `$F/ingestion-summary.md` and `$F/raw-response.md`, outside `$F/run-1`.
5. Skill step 5 passes to the Tester. The coordinator runs no `render`, no `validate` and no scoring.

Unless the coordinating session started after the ingestor was persisted, the evidence states that the agent definition actually loaded is unproven, and that the hash covers only the file on disk.

**Scored by the Tester.** Every block starts with the same variables, and each command is run as written from the repository root in bash or zsh. Set `F` first in every shell call. `grep -c` prints 0 and exits 1 when nothing matches, so that exit status alone is not a failure in the rows expecting 0.

```sh
F=.checks/US-1.2/forward
R="$F/run-1"
B="$F/before"
INGESTOR=.claude/agents/autobots-spec-ingestor.md
SKILL=.claude/skills/autobots-spec-ingest/SKILL.md
MANIFEST=docs/engineering/evidence/US-1.2/reviewed-manifest.json

python3.12 scripts/specs.py render --project-root "$R" --path SPECS.md
python3.12 scripts/specs.py validate --project-root "$R" --path SPECS.md
shasum -a 256 -c "$F/delegation.sha256"

test "$(jq -r --arg p "$INGESTOR" '.files[$p]' "$MANIFEST")" = "$(awk -v p="$INGESTOR" '$2 == p {print $1}' "$F/delegation.sha256")"

git diff --quiet HEAD -- "$SKILL"
test "$(git show "HEAD:$SKILL" | shasum -a 256 | awk '{print $1}')" = "$(awk -v p="$SKILL" '$2 == p {print $1}' "$F/delegation.sha256")"

diff <(grep -E '^(# EPIC-|### US-)' "$B/SPECS.md") <(grep -E '^(# EPIC-|### US-)' "$R/SPECS.md")
diff <(grep -E '^\| \[SP-' "$B/SPECS.md") <(grep -E '^\| \[SP-' "$R/SPECS.md")
diff <(grep -oE 'SP-[0-9]+' "$B/SPECS.md" | sort -u) <(grep -oE 'SP-[0-9]+' "$R/SPECS.md" | sort -u)

awk '/^### US-/{id=$2} /^Dependencies:/{d=1;next} /^Tasks:/{d=0} d&&NF{print id, $0}' "$B/SPECS.md" > "$F/deps-before.txt"
awk '/^### US-/{id=$2} /^Dependencies:/{d=1;next} /^Tasks:/{d=0} d&&NF{print id, $0}' "$R/SPECS.md" > "$F/deps-run.txt"
diff "$F/deps-before.txt" "$F/deps-run.txt"

awk '/^### US-/{id=$2} /^(Status|Change):/{print id, $0}' "$R/SPECS.md"
```

```sh
F=.checks/US-1.2/forward
R="$F/run-1"
B="$F/before"

python3.12 scripts/specs.py validate --project-root "$B" --path SPECS.md
grep -c '^## SP-' "$B/CONTRACT.md"
grep -c 'When the composer draft changes' "$B/PRD.md"
grep -F 'US-1.3: - US-1.2' "$F/deps-before.txt"

python3.12 tests/harness/forward_arrangement.py "$F/rerun"
diff -r "$B" "$F/rerun"

shasum -a 256 "$R/SPECS.md" > "$F/rendered.sha256"
python3.12 scripts/specs.py render --project-root "$R" --path SPECS.md
shasum -a 256 -c "$F/rendered.sha256"

cp -R "$R" "$F/stale"
sed -i '' 's/^Status: READY$/Status: BLOCKED/' "$F/stale/SPECS.md"
python3.12 scripts/specs.py validate --project-root "$F/stale" --path SPECS.md
python3.12 scripts/specs.py render --project-root "$F/stale" --path SPECS.md
python3.12 scripts/specs.py validate --project-root "$F/stale" --path SPECS.md

grep -c '^Status: DONE' "$R/SPECS.md"
grep -c '^- \[[xX]\]' "$R/SPECS.md"
diff -r -x SPECS.md "$B" "$R"
```

| Check | Command or method | Expected | Class |
|---|---|---|---|
| Given arranged | The first four commands of the second block | Exit 0; 2; 1; `US-1.3: - US-1.2` present | `disposable` |
| Arrangement reproducible | The arrangement rerun and `diff -r` in the second block | No difference | `disposable` |
| Bound on disk | `shasum -a 256 -c` in the first block | Exit 0: the ingestor and skill on disk still match what was recorded at delegation | `static` |
| Bound to definitions: ingestor | The `jq` and `awk` comparison in the first block | Exit 0: the hash recorded at delegation equals the file's entry in the reviewed manifest, so the exercise ran against the reviewed ingestor | `static` |
| Bound to definitions: paired skill | The `git diff --quiet` and `git show` comparison in the first block. The skill is expected unchanged, so `current_files` in `scripts/story_manifest.py` leaves it out of the manifest, and a manifest comparison cannot apply | Both exit 0: the skill is unchanged from `HEAD`, and the hash recorded at delegation equals `HEAD`'s blob | `static` |
| Validates | `render`, then `validate`, in the first block | Exit 0: sources resolve, Gherkin is valid | `disposable` |
| Navigation | The `rendered.sha256` commands in the second block; read `$R/SPECS.md`'s Table of Contents, status table and diagram | Second render changes nothing; the new story and its `US_1_2 -.-> US_1_5` edge appear | `disposable` |
| Stale navigation failure and recovery | The `$F/stale` commands in the second block | First `validate` exits non-zero, then `render` and `validate` exit 0 | `disposable` |
| Stable identity | First `diff` in the first block | Only added lines, for the new story. `EPIC-1` and US-1.1 to US-1.4 kept with their titles | `disposable` |
| SP coverage preserved | Second and third `diff` in the first block | No difference: SP-901 and SP-902 with their rows. A lost or rewritten row fails | `disposable` |
| Honest dependencies | The `deps` `diff` in the first block | The only difference adds `US-1.5: - US-1.2`. A dropped or invented dependency fails | `disposable` |
| Honest statuses | The final `awk` in the first block | The expected result above, including the `Change:` line under US-1.2 | `disposable` |
| New story cites its source | Read its `Source:` and Gherkin | Cites REQ-06; ordered Given, When, Then, each supported by REQ-06, including its stated trigger | `disposable`, by inspection |
| Nothing invented | Read the copy's stories against its `PRD.md`, `CONTRACT.md` and `CODEBASE.md` | The seven-retry prototype is not a requirement; each scenario traces to a cited source | `disposable`, by inspection, since entailment is not mechanically decidable |
| No delivery claim | The two `grep -c` commands in the second block, and reading `$F/ingestion-summary.md` | 0 and 0; the summary claims no delivery and says validation was not run by the agent | `disposable` |
| Field-order test | The ingestor test in `tests/harness/test_assistant_assets.py`, whose failure on the base file task 1.5 records | Passes on the final file | `static` |
| Read-only and pairing | Unit tests; inspection of the ingestor's frontmatter | Only Read, Grep, Glob; skill owns persistence | `static` |
| Other sources untouched | `diff -r -x SPECS.md` in the second block, which includes the hidden file | No difference | `disposable` |
| Real backlog untouched by ingestion | `shasum -a 256 SPECS.md` against `.checks/US-1.2/specs-before.sha256`, allowing only the coordinator's status lines by `git diff` | No ingestion output in the real file | `static` |
| No product code | `git status --short` compared with `.checks/US-1.2/status-before.txt`; `test ! -e apps`, `test ! -e services` | Only Affected Files paths | `static` |
| Retained fixture | `python3.12 scripts/specs.py validate --project-root docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture` | Exit 0: 1 epic, 4 stories, 13 tasks | `static` |

One run shows one output, not that the ingestor is reliable. Synthetic `SP-*` sections show that coverage survived on this fixture, not that the real SP coverage would. Read-only tools rest on the frontmatter; no check observes that the live delegation stayed read-only other than `git status` and the source `diff` afterward.

### DH-W05 runbook

The procedure is `docs/engineering/runbooks/development-harness.md`, updated because operating behavior changes: the report gains a field. Regression check: `python3.12 scripts/verify.py --profile harness`. The runbook must be final at capture, and links to `docs/engineering/evidence/US-1.2/summary.md` for exercise status rather than recording it. That means replacing its existing "Evidence and last exercise" section, which records an exercise date and points to HARNESS-ADAPT-001 as the latest evidence. HARNESS-ADAPT-001 may stay linked as earlier evidence, not as current status. The link to the summary resolves only once the coordinator writes the summary after testing; task 1.2's link test does not cover the runbook, and the evidence review checks that link. Inspection, plus `grep -c 'Last exercised' docs/engineering/runbooks/development-harness.md` printing 0.

Task 2.3 runs the runbook's non-delegation commands as written with `F=.checks/US-1.2/runbook-check/forward`, so that the rehearsal leaves `.checks/US-1.2/forward` free for the real run. The two comparisons that read `reviewed-manifest.json` need capture, so task 2.3 reports them as not yet run and the Tester runs them.

The Tester exercises "Validate the backlog", "Run the delivered checks", the adapter-status steps and the forward procedure's non-delegation steps, plus stale navigation as the failure and recovery path. The evidence records which steps ran and which did not. The delegation step is performed by the coordinator and reported that way. Live assistant event delivery stays unexercised and is reported that way.

### Evidence summary must state

- The seven coordinator decisions, that they were not put to the user, that none is a user ruling, and that each is open for the user to overturn.
- Decision 2's reliance on the bridge sentence marked "Coordinator's wording, not put to the user", and that overturning it changes the score and the records, not the code.
- Scenario "Separate optional assistant activation" covers arranged conditions; no real adapter was inactive on this machine.
- The model route was not checked.
- The result of each CLI control pair and the CLI version. If the fallback applied, that DH-04's "qualified CLI" clause is not met, as an open limitation, with its nearest basis in US-1.2#2 and H0.2.
- The two qualification literals are not a complete list of observations: one plugin `PreToolUse` event, later hook runs and this story's delegations were observed, and none of that qualifies delivery.
- Whether the loaded ingestor definition is proven or not.
- The carried edits' deviation.
- Results by DH-09.2 class, keeping `static`, `mock`, `disposable` and `live` distinct.

### Review Scope

Give the reviewer the manifest, fingerprint and `.checks/US-1.2/changed.txt`, and use `check-scope --diff` with that file. Also hand it the paths `docs/engineering/evidence/US-1.2/dh-04-table.md` and `docs/engineering/evidence/US-1.2/common-rules-table.md`, because `is_record` excludes them from the manifest and `changed.txt`. The review covers:

- Each protected file in the manifest as implementation. The coordinator is not its reviewer.
- The two tables, each repeated by reading the files.
- `.claude/rules/ohmyorch-delivery.md` and `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md`, for the coordinator's edits carried from US-1.1: F-11 (the reading of "loop delivery one epic by epic until complete all"), F-12 (separating the user-confirmed sentence from the coordinator's wording), and the "any required item" and research-payload rulings.

## Dependencies

- US-1.1: `DONE`.
- Local tools already present: Python 3.12, Git, jq, OpenSpec 1.13.2. Claude CLI only for `--version` and `plugin validate`, and delegation of the project's `autobots-spec-ingestor` for the forward exercise.
- Ordering: the CLI control and the DH-04 table precede authoring. Rule checks are red until the protected content lands. The final common-rule run follows the runbook and page. The forward exercise follows capture, because the ingestor must be final.
- External: None identified.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `claude --version` under reduced environment fails, so the real machine reads `inactive` falsely | low | medium | The Planner observed exit 0 and the version with only `PATH` set. The Implementer reobserves in pass 2 and never adds credentials. Status never fails verification |
| `claude --version` makes an outbound check, as `supabase --version` appears to. Not captured | low | low | Bounded timeout; failure gives `inactive`. Record as unknown |
| A full harness run under `PATH=/usr/bin:/bin` fails. Not run during planning, because it overwrites the report | low | medium | `git` resolves there, and `git grep` finds no test naming `python3` or `python3.12`. A failure is a finding for the Tester to report |
| The running session holds an older ingestor definition, so the hash and the behavior differ. The critique recalled this from documentation, unverified | medium | medium | Evidence states the loaded definition is unproven unless the session started after the edit |
| A strict reading of a skill or agent finds a DH-04 gap in a file the plan does not name | medium | medium | Task 1.7 runs before authoring and stops for a plan amendment. Found at review, it takes the reopen route |
| Closing a skill's gap adds new behavior | low | medium | Task 1.8 restricts additions to rule `paths`, DH-03's record paths for the two skills with no matching rule, and existing contract text. Reviewer checks |
| Links to unimplemented profiles look like working checks | medium | medium | Rules name the profile and the runner, and the review responsibility applies today. Tester runs all listed profiles to show they fail |
| Allowed-target check passes on a formal but unhelpful link | medium | low | Reviewer inspects each link's fit; the test states it only proves presence |
| `claude plugin validate` empty `contents` is a vacuous pass, and whether a manifest changes that is untried | high | medium | Two paired controls in pass 1. If neither discriminates, decision 4 applies: DH-04's "qualified CLI" clause is reported as not met, as an open limitation |
| The plugin-shaped good copy fails `--strict` for a reason other than frontmatter, such as missing manifest metadata | medium | low | Task 2.6 allows added manifest metadata only, never a changed skill or agent, and the keys are reported. A failure from a copied skill or agent is a finding, and that pair does not count |
| `config_errors` treats any unrelated error as `configuration_invalid` | medium | low | Deliberately conservative, and the `errors` list names the cause. Runbook explains |
| Allowlisted qualification literals make a later story's honest change fail | medium | low | Intended: a later claim needs a deliberate change to the check. Stated in the test's docstring |
| Harness red between implementer passes triggers Stop-hook blocks | high | low | Expected and stated. Coordinator continues to the next step |
| Ingestor output fails `validate`, drops an arranged fact, or differs in ways not attributable to the change | medium | medium | That is a real finding. Report it; do not hand-repair the copy to pass. Fixture copy stays disposable |
| Coordinator as paired caller is read as the coordinator testing | low | medium | Decision 5: the coordinator only delegates and persists verbatim. The Tester runs `render` and `validate` and scores. Recorded as such. It was not put to the user |
| A coordinator decision is overturned later | medium | medium | All seven are recorded and reported as the coordinator's. Overturning decision 2 rescores the scenario and changes records, not code. Rejecting decision 4's fallback, if it applied, blocks the story. A change that affects acceptance goes through a blocking review and reopen |
| Editing `./CLAUDE.md` disturbs the managed block | low | medium | Edit outside the markers; diff check and doctor |
| The new test module asserts on real files, so later stories' rule changes must keep it green | low | low | Intended regression value. Pending profiles are read from configuration, so US-1.4 or later implementing one does not break it |
| Hanging-stub test exceeds `run_check`'s 60-second limit | low | medium | New session with process-group kill, and an injected short timeout |
| Scoped check `check-scope` treats every named path as predicted | high | low | The `git diff --quiet` block names every expected-unchanged path, and the `git status` row covers the rest |
| The runbook's rehearsal uses up the real run's directory | low | low | Task 2.3 rehearses under a separate `F`; the script's refusal of an existing destination makes a collision visible |

## Open Questions

None blocks implementation. The planning questions were decided by the coordinator, as listed under Settled decisions, not by the user. They were not put to the user, so the final report repeats them for the user to confirm or overturn.
