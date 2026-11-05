# Implementation Plan — us-1-1-h0-repository-prerequisite-inventory

Story: US-1.1
Change: us-1-1-h0-repository-prerequisite-inventory

## Selected Story

US-1.1: H0 repository and prerequisite inventory (EPIC-1, phase reference H0-01). Sources: SP-001 item 1, DH-02 H0.1, SP-020. This change adds the inventory the story asks for, evaluates which hygiene configuration is missing, and adds the five cache ignore rules the user decided belong in this story.

Acceptance, quoted from `SPECS.md`:

```gherkin
Scenario: Preserve existing work
  Given the documentation and project-local development assets already present
  When the repository and installed tool versions are inspected
  Then the inventory records actual paths, versions and missing prerequisites without secret values or overwritten unrelated settings

Scenario: Establish repository hygiene
  Given version control or required ignores are absent
  When the H0 foundation is prepared
  Then version control and ignores are established without committing credentials, local transcripts or disposable data
```

Settled decisions this plan applies:

- **Cache ignores (user, 2026-11-04, review F-6):** DH-03 says "caches" with no in-use limit, so this story adds rules for `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo` and `.pnpm-store/`. Recorded in Decision 0002.
- **Cache list (user, 2026-11-04):** those five close the cache question for US-1.1. A later story that introduces a tool adds that tool's ignores. No record may say every cache is covered.
- **OQ-1 (user):** local transcripts are recorded as not missing, and no ignore rule is added. That rests on the user's decision, not on a probe: the samples exit 1 before and after this change. The inventory states the gap.
- **A1 (coordinator):** the inventory lives at `docs/engineering/prerequisite-inventory.md`.
- **A2 (coordinator):** DH-W05 is met by reference to `docs/engineering/runbooks/development-harness.md` plus `python3.12 scripts/verify.py --profile harness`. No new runbook.
- **Protected paths (user):** `.gitignore` is a protected path and is implementation content for this story. The Implementer authors its lines and returns them under a heading naming the path, the coordinator writes them verbatim before capture, and the reviewer checks them as implementation. No other protected path is implementation content here.
- **Unmet-Given exception:** does not apply. The hygiene scenario's Given holds for the five cache categories, and the Tester scores the scenario from what it observes.

## OpenSpec Artifacts

- `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/proposal.md`: scope, non-goals, observed baseline, settled decisions.
- `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/specs/repository-prerequisite-inventory/spec.md`: two requirements, each carrying one of the story's scenarios.
- `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/tasks.md`: seven original tasks, ticked, plus nine R1 remediation tasks. R1.1 to R1.6 are this round's implementation work, and R1.7 to R1.9 were done by the coordinator. Original task text and ticks stay as they are.
- `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/history/review-r1.md`: the `changes-requested` review behind the R1 tasks. Its fingerprint and `history/test-report-r1.md` do not cover this round.
- `design.md`: intentionally absent. No external contract changes, and the schema makes it conditional.

`openspec validate us-1-1-h0-repository-prerequisite-inventory --strict` was observed to pass at planning time. Base revision is `34ae38f`.

## Implementation Order

Coordinator, first: persist the revised proposal and this plan. R1.7 to R1.9 and the Decision 0002 entry are already in place.

Implementer, first pass (authoring only):

1. Record this round's starting state with `git status --short > .checks/US-1.1/status-before-r1.txt`.
2. R1.1: save the five lines to `.checks/US-1.1/gitignore-lines.txt`, pre-test them (see the hygiene Test Strategy), and return them under a heading naming `.gitignore`. State what could not be tested because the file was not yet in place. Do not tick R1.1 or edit the inventory yet.

The lines to add, directly after line 24 (`# OHMYORCH:END ignores`) at the end of the file, outside the managed block, with no blank line and no comment:

```gitignore
.pytest_cache/
.ruff_cache/
.mypy_cache/
*.tsbuildinfo
.pnpm-store/
```

Coordinator: append those lines verbatim and change nothing else in the file. Record in the Implementation section that `.gitignore` was persisted this way. A needed change goes back to the Implementer.

Implementer, second pass:

3. R1.1: run the hygiene probes against the real file. Tick R1.1 only if they match. On a mismatch, report it and do not tick.
4. R1.2 and R1.4: rewrite the hygiene account from the observed results, so the inventory records nothing it has not observed.
5. R1.3, R1.5 and R1.6: make the three accuracy corrections.
6. Re-run the secret-shape check on the final inventory, the revised overwrite check, and the commands from task 2.3.

Coordinator, before capture: write the Implementation section and land any remaining `CODEBASE.md` or Decision 0002 edit, since later edits fail `compare`. Then capture afresh. Review and testing both restart, for both scenarios.

## Task to Acceptance Mapping

| Task | Acceptance criterion | Notes |
|---|---|---|
| 1.1 Repository section | Scenario: Preserve existing work | Records actual paths of existing assets. Must state that presence is not H0/H1 qualification |
| 1.2 Tool table | Scenario: Preserve existing work | Records paths, versions and missing prerequisites. `pnpm` was missing at planning time. No compatibility verdict, which is US-1.3 |
| 1.3 `CODEBASE.md` reconciliation | Scenario: Preserve existing work | Serves the story's Codebase Context ("reconcile current tooling"). Compares only; `CODEBASE.md` stays coordinator-owned |
| 1.4 Secret and overwrite checks | Scenario: Preserve existing work | Serves "without secret values or overwritten unrelated settings". Ticked. Its `.gitignore` no-change check is superseded by R1.1 and now exits non-zero as expected |
| 2.1 Given evaluation | Scenario: Establish repository hygiene | Evaluates the Given clause. See the Test Strategy for what this does and does not show |
| 2.2 Prepare only what is missing | Scenario: Establish repository hygiene | Ticked with the outcome no change, which review F-6 found wrong. R1.1 supersedes that outcome. The tick and text stay |
| 2.3 Backlog and harness checks | Scenario: Preserve existing work; Scenario: Establish repository hygiene | Harness evidence only, not H0/H1 or product acceptance |
| R1.1 `.gitignore` rules (F-6) | Scenario: Establish repository hygiene | Establishes the five rules. Protected-path procedure |
| R1.2 Inventory hygiene account (F-7) | Scenario: Establish repository hygiene; Scenario: Preserve existing work | Records the five rules as added under the user's decision and transcripts as still without a rule by OQ-1 |
| R1.3 `supabase --version` network note (F-1) | Scenario: Preserve existing work | The reproduction record states what its probe does |
| R1.4 Cache row label (F-2) | Scenario: Preserve existing work | Label states observed rule status, not "in use" |
| R1.5 `CODEBASE.md` sentence (F-3) | Scenario: Preserve existing work | Sentence is scoped to this comparison |
| R1.6 Scripts reconciliation row (F-8) | Scenario: Preserve existing work | Separates the three entry points from the imported `harness_lib.py` |

Mapped: tasks 1.1 to 1.4, 2.1 to 2.3 and R1.1 to R1.6. Mapped to no scenario: R1.7 to R1.9 (F-4, F-5, F-9). They are coordinator corrections to delivery rules and decision records, done already, and they change no product or acceptance behavior.

## Affected Files

Expected scope, based on the persisted artifacts, the review and the write-scope check. The Implementer is expected to write only the inventory and `tasks.md`, and to author the `.gitignore` lines for the coordinator to write.

| Path | Expected change | Evidence |
|---|---|---|
| ./.gitignore | Five lines appended after `# OHMYORCH:END ignores`. **Protected path**: the Implementer authors, the coordinator writes verbatim, the reviewer checks as implementation | Review F-6; bridge rule `Protected paths`; `check-write-scope` returned BLOCKED for the Implementer. Written with `./` because `check-scope` only recognises path tokens containing a slash |
| `docs/engineering/prerequisite-inventory.md` | Likely edits to the hygiene, tool-note, reconciliation and reproduction text | R1.2 to R1.6. `check-write-scope` returned ALLOW |
| `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/` | Implementer ticks R1 tasks in `tasks.md`. Coordinator owns the plan, proposal, `status.md` and `history/`; reviewer and tester add new verdicts | Directory read; write-scope rule for selected tasks |
| `SPECS.md` | Coordinator-owned status and task edits | Already modified by `select`; ticked at `mark-done` per the bridge rule |
| `CODEBASE.md` | Coordinator-owned. Already holds the revision, note and inventory pointer | `git diff`; write scope blocks the Implementer and allows the coordinator |
| `openspec/delivery/goal.md` | Coordinator-owned derived state | Written by `ohmyorch delivery`; currently untracked |
| `docs/engineering/work-items/US-1.1.md` | Coordinator-owned DH-W record, including which paths were persisted through the protected-path procedure | Bridge rule, Records and `Protected paths` sections |
| `docs/engineering/evidence/US-1.1/` | Coordinator-owned evidence summary, plus a fresh `reviewed-manifest.json` from `capture` | Bridge rule; `is_record()` in `story_manifest.py` |
| `.claude/rules/ohmyorch-delivery.md` | Coordinator decision record, already edited. Not part of this story's acceptance | `git status`; section read |
| `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` | Coordinator decision record, already edited. Not part of this story's acceptance | `git status`; entries read |

Expected unchanged: the Git configuration, the managed `OHMYORCH` block and lines 1 to 24 of `.gitignore`, `.claude/settings.json`, `.claude/settings.local.json`, `docs/engineering/runbooks/development-harness.md`, and everything under the script and test directories.

**Generated output.** All of it is Git-ignored, so none of it should affect `compare`:

- `.checks/harness/latest.json`, written by `scripts/verify.py`.
- `.checks/US-1.1/status-before-r1.txt` and `.checks/US-1.1/gitignore-lines.txt` from this plan, and `.checks/US-1.1/changed.txt` from the coordinator's capture step.
- Bytecode under the existing ignored `__pycache__` directories, because `verify.py` itself imports `harness_lib`.

The new rules generate nothing, and no cache tool is run. The version probes may write caches in the home directory, outside the repository.

## Test Strategy

All evidence for this story is `static`, with model transport `none`. The story has no executable product behavior, so most checks are re-run probes plus inspection of the document.

### Probe rules for the Implementer and Tester

The project hook denies any Bash command whose text names the provider master-key file, and any `cat`, `head`, `tail`, `less` or `more` of a `.env` path. The Read tool is denied on those files too. To stay clear of it:

- Do not name, locate, open or test the provider master-key file. The inventory records it from `PRD-Model-Providers.md` as outside the repository and not probed. Write it in prose as "the provider master-key file".
- Treat `.env` paths as path strings only, with `git check-ignore -q --no-index`. That form passed the hook at planning time.
- If a probe is denied, leave it out and report it. Do not rephrase, encode or split the command to get past the hook.

Also never run:

- `env`, `printenv` or anything that prints `PATH`
- `git remote -v` or `git config` dumps (use `git remote` for names only)
- `docker version` or `docker info`, which contact the engine
- any `corepack` command other than `--version`, and never `corepack pnpm`
- any install or service start
- anything that reads `.claude/settings.local.json`

The shell is zsh, and `python3` is an alias there. Run each install by absolute path, and use `which -a <tool>` to find installs. Record the alias as a separate note.

### Scenario: Preserve existing work

| Check | Command or method | Expected |
|---|---|---|
| Recorded paths exist | `test -e <path>` for each recorded path | Every path exists |
| Counts are accurate | `git ls-files \| awk -F/ '{print $1}' \| sort \| uniq -c` | Matches the inventory (159 tracked files at planning time) |
| Tool versions | Re-run each recorded absolute-path version command | Same output. A mismatch is reported, not silently reconciled |
| Missing prerequisite | `command -v pnpm` | Non-zero exit; recorded as missing |
| No secret-shaped values | `grep -l -E 'sk-or-v1-[A-Za-z0-9]{16,}\|sk-ant-[A-Za-z0-9_-]{16,}\|-----BEGIN [A-Z ]*PRIVATE KEY-----\|ghp_[A-Za-z0-9]{20,}' docs/engineering/prerequisite-inventory.md` | Exit 1, no file listed. Remove the table-escape backslashes before running |
| Nothing unrelated overwritten | `git diff --quiet HEAD -- .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests` | Exit 0. `.gitignore` is checked under the hygiene scenario |
| Only planned paths added | `git status --short` compared with `.checks/US-1.1/status-before-r1.txt` | Differences limited to paths in Affected Files |
| Scope | `check-scope --diff .checks/US-1.1/changed.txt` | No unpredicted path |
| Reconciliation is complete | Inspection: each statement under `Runtime and Tooling` in `CODEBASE.md` has a row | All covered. Inspection because this is a document comparison |
| No compatibility verdict | Inspection of the tool table | None present |

Two limits apply:

- The secret-shape scan is narrow, so a clean result does not prove absence. The inventory must say so.
- Non-overwrite of `.claude/settings.local.json` cannot be shown mechanically. It is ignored, must not be read, and can legitimately change through assistant permission approvals. The evidence is limited to no write being attempted, which the reviewer checks by inspection.

The `check-scope` row is weaker than it looks, because any path named in this plan counts as predicted. The `git diff --quiet` row covers the named paths that must not change.

### Scenario: Establish repository hygiene

**The Given holds, so the unmet-Given exception does not apply.** At base revision `34ae38f`, `.gitignore` had no rule for five cache categories covered by DH-03's "caches". This story establishes those five rules and nothing else. Version control and all other rules predate it. The Tester scores the scenario from what it observes. This plan does not pre-score it.

Evidence that the Given held at the base revision:

```sh
git show 34ae38f:.gitignore | grep -cE '^(\.pytest_cache/|\.ruff_cache/|\.mypy_cache/|\*\.tsbuildinfo|\.pnpm-store/)$'
```

Expected output: `0`. The grep exits 1 on a zero count, so read the output rather than the exit code.

Implementer pre-test, before the file is in place. This is not acceptance evidence:

```sh
git -c core.excludesFile="$PWD/.checks/US-1.1/gitignore-lines.txt" check-ignore -q --no-index <sample>
git ls-files -ci --exclude-from=.checks/US-1.1/gitignore-lines.txt
```

Probes against the real file:

| Item | Probe | Expected | Basis |
|---|---|---|---|
| Five cache rules | `git check-ignore -q --no-index <p>` for `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo`, `apps/web/tsconfig.tsbuildinfo`, `.pnpm-store/x` | Exit 0 for each | Observation. Established by this story |
| Other required ignores with a concrete path | Same probe for `.env`, `.env.local`, `.claude/settings.local.json`, `.checks/x`, `.venv/x`, `node_modules/x`, `.next/x`, `scripts/__pycache__/a.pyc`, `x.log`, `.DS_Store`, `infra/supabase/volumes/x`, `supabase/.temp/x`, `supabase/.branches/x` | Exit 0 for each, as before | Observation. Predates this story |
| `.env.example` | Same probe | Exit 1, as before | Observation. Kept by the `!.env.example` rule |
| Local transcripts | Same probe for `transcript.jsonl`, `transcripts/x.md`, `.claude/projects/x.jsonl` | **Exit 1 for each: no rule exists** | **User decision OQ-1, not observation** |
| Version control | `git rev-parse --is-inside-work-tree` | `true` | Observation. Predates this story |
| No tracked file is ignored | `git ls-files -ci --exclude-standard` | No output, exit 0 | Observation, from review F-6 |
| Placement | `grep -n 'OHMYORCH:END' .gitignore` and `sed -n '25,$p' .gitignore` | `24:` on the marker line; the five rules follow in the order above | Observation |
| Provider master-key file | Not probed | Not applicable | `PRD-Model-Providers.md` places it outside the repository |

Only those rules were added:

```sh
git diff -U0 HEAD -- .gitignore | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)'
```

Expected output: the five rules, each prefixed `+`, and no `-` line.

Nothing forbidden was committed. These are name scans only, and a credential or transcript under an unremarkable name would not appear:

- `git log --all --name-only --format= | sort -u | grep -i -E '(^|/)\.env|\.key$|\.pem$|\.p12$|secret|credential|transcript|\.jsonl$|\.sqlite|\.db$|/volumes/|settings\.local'` listed only `research/qwen38-gguf-memory.jsonl` at planning time.
- The same filter over `.checks/US-1.1/changed.txt` should list nothing and exit 1.

**What remains not established:**

- **Local transcripts:** no rule exists, and the inventory, Tester and evidence summary must attribute "not missing" to the user's decision OQ-1, not to a probe. A future in-repository transcript location is uncovered until a rule is added.
- **Other caches:** DH-03 gives no closed list. `.eslintcache`, `.coverage`, `coverage/x`, `.hypothesis/x`, `.cache/x`, `.turbo/x` and `.uv/x` exited 1 at planning time and are not added, by the user's decision that a later story introducing a tool adds its ignores. No record may say every cache is covered. These are not findings for this story.
- **Real tool behavior:** the rules are shown on sample paths only. No cache tool exists in this repository, so none is run.
- **Version control:** this story did not establish it, and no record may say otherwise.

No separate fixture is planned, because the rules are added to this repository and probed directly.

### Backlog, harness and runbook

- `python3.12 scripts/specs.py validate` and `python3.12 scripts/verify.py --profile harness` must both exit 0. Reported as harness evidence only. They say nothing about the inventory's accuracy.
- `python3.12 scripts/verify.py --profile db` is not part of this story.
- DH-W05: the Tester exercises `Run the delivered checks` in `docs/engineering/runbooks/development-harness.md` and re-runs the inventory's recorded probes, with results in `test-report.md`. Operating behavior is unchanged, and the runbook is not edited.

### Inventory content the Reviewer can check

The document must include: observation date and base revision, the shell used, the commands that reproduce each result, the statement that presence is not qualification, the secret-scan limit, the five rules recorded as added under the user's decision, the local-transcripts gap attributed to OQ-1, the statement that DH-03 gives no closed cache list, the note that the provider master-key file was not probed, and the `supabase --version` network note. Home-directory paths are recorded verbatim (A3).

## Dependencies

- Story dependencies: none (`SPECS.md`).
- Internal: this plan and the open work item must exist before the inventory write, per the planning-handoff guard and the bridge rule.
- External: no install, service, database, credential or model call is needed. `supabase --version` appears to make an outbound update check: with network denied it printed the version with no update notice (review F-1). That is inferred from behavior, not a packet capture, and no other version probe was tested for this. Each re-run repeats the request, and no source forbids it.

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The transcript gap is read as established | medium | high | Required attribution to OQ-1 in the inventory, test report and evidence summary; reviewer checks it |
| The inventory records results before `.gitignore` is in place | medium | medium | Two Implementer passes, with the hygiene rewrite after the coordinator's write |
| `.gitignore` content is altered, or lands inside the managed block | low | medium | Verbatim write; the placement and diff probes; changes go back to the Implementer |
| Later plugin upgrade disturbs the appended lines | low | low | `managed-files.sh` replaces only the text between its markers. Read in code, not exercised |
| Ticked tasks 1.4 and 2.2 are read as current | medium | low | The mapping marks them superseded by R1.1 |
| `supabase --version` makes an outbound request on each re-run | high | low | R1.3 discloses it. Others are untested, and the inventory says so |
| Probe results vary by shell and PATH, given several Node, uv and Python installs | medium | medium | Record the shell, every install and absolute-path versions. Report mismatches |
| Coordinator edits land after capture and fail `compare` | medium | medium | Land them before capture, as ordered above |
| `check-scope` misses an edit to a path this plan names | low | medium | The `git diff` checks; this plan avoids naming bare directories |
| Secret-shape scan misses a credential format | low | high | State the limit in the inventory. The filename scan is a second, also limited, signal |
| Inventory goes stale, and its tracked-file counts stop matching `git ls-files` after the story commit | high | low | It is a point-in-time record tied to its base revision. Later checks use `git ls-tree -r --name-only 34ae38f` (159 at planning time) |
| A probe is denied by the project hook | low | low | Probe rules above. Leave it out and report it |

## Open Questions

None open.

Decided: scoring of "Scenario: Establish repository hygiene" under the unmet-Given exception no longer applies, because the Given holds. Local transcripts stay as the user decided (OQ-1): no rule. The five cache rules close the cache question for this story (user decision).
