# Review — us-1-1-h0-repository-prerequisite-inventory

Change: us-1-1-h0-repository-prerequisite-inventory
Story: US-1.1
Verdict: pass
Blocking: None
Coverage: 2/2 acceptance criteria evaluated
OpenSpec verify: VERIFIED in the checks that ran: 0 critical, 0 warnings, tasks 16/16, requirements 2/2, `openspec validate --strict` valid. Design Adherence not verified because `design.md` is intentionally absent, so readiness for archive is not claimed. Steps followed by hand from the skill text because this agent has no skill-invocation tool.
Reviewed fingerprint: 09b978de1c9eaa4bb57629ff84b058a57a9b9f4ee58002fbbbfa86238a72de2c

Reviewer: `ohmyorch:reviewer`, a delegated context separate from the implementer and coordinator. Evidence is static or a re-run local probe, with model transport none. This is reopen round 1. `history/review-r1.md` and `history/test-report-r1.md` were treated as prior claims and rechecked.

## Summary

The implementation satisfies both scenarios. Every recorded inventory value re-run here matched, and the five `.gitignore` rules are in place, verbatim and outside the managed block. Version control and the other rules predate the story and no record says otherwise. Local transcripts have no rule and are "not missing" by decision OQ-1 only, as the inventory says.

All nine findings from round 1 are resolved in the files, except that R1.9's user confirmation of the new wording has no record (F-12). There are four non-blocking findings: stale statements in the work item, a false summary sentence in Decision 0002, that missing confirmation record, and one loose provenance sentence in the inventory. None makes acceptance false or breaches a boundary, and I found no contradiction with `AGENTS.md`.

## Findings

All four are non-blocking. `docs/engineering/work-items/US-1.1.md` is a record outside the manifest, so F-10 and F-12 can be fixed without a recapture. Decision 0002 and the inventory are in the manifest, so editing them now fails `compare` and needs the reopen route. F-11 and F-13 are low enough to carry forward if the coordinator records that disposition.

### Finding F-10: the work item still states the superseded outcome of the hygiene scenario

Severity: medium, non-blocking at this gate. Owner: coordinator. Fix before the evidence review.
Requirement: DH-W02, an implementation record of actual resulting behavior; the plan's settled decision "Unmet-Given exception: does not apply" (`implementation-plan.md` line 32).
Observed: `docs/engineering/work-items/US-1.1.md` keeps these statements as current text:
- Line 15, under the Plan's decisions: the scenario "is expected to be `UNVERIFIED` under the unmet-Given exception, because version control and ignores already exist (user)". This contradicts plan lines 32 and 168.
- Line 25: "no protected path was used". Line 38 of the same file records `.gitignore` going through that procedure.
- Line 29: "Version control and ignores already existed and predate this story, so it established nothing". `.gitignore` lines 25 to 29 are new in this story.
- Lines 44 and 48 to 56: the verdict `pass`, 1/2 coverage, and dispositions "Accepted" and "Carried forward" for findings that this round fixed.

Line 60 says a later user decision supersedes the outcome, but it names only "answer 2". Lines 13 to 17 also omit the cache decisions.
Expected: a reader of the committed record can tell what the story actually did. Round-0 text is either marked as such or replaced.
Consequence: the tester and evidence reviewer are told by this record that the scenario should be `UNVERIFIED` and that nothing was established. That is the wrong score and the wrong behavior.
Remediation: Coordinator: mark lines 15, 25, 29, 44 and 48 to 58 as round-0 and superseded, or rewrite them, and add both cache decisions to the Decisions list. The Review section is due after `test` anyway.

### Finding F-11: Decision 0002 says all five decisions are recorded in the bridge rule, and they are not

Severity: low, non-blocking. Owner: coordinator.
Requirement: consistency of decision records; `.claude/rules/ohmyorch-delivery.md` is named as the resolving record by Decision 0002 line 21.
Observed: `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` line 38 reads "All by the user on 2026-11-04, and all recorded in the bridge rule". The bridge has the protected-path decision (lines 39 to 46) and the unmet-Given decision (line 71). A search of the bridge for transcript, cache and all-epics terms finds only the word "cached" at line 10, so Local transcripts, Cache ignores and Delivery targets (lines 42 to 44) are not there. Bridge line 24, "A story that adds tooling adds its ignores", is a general rule, not the cache decision. Separately, line 7 says a target is authorized "only when the user names it on `/ohmyorch:deliver`", and line 44 says the user named all epics without saying whether that amends line 7.
Expected: the sentence is true as read, and the two authorization statements agree.
Consequence: a reader looking for the transcript or cache decision in the bridge finds nothing. Later epics could be read as either authorized or not.
Remediation: Coordinator: change line 38 to "the first two are also in the bridge rule", and state on line 44 that the naming applies to `/ohmyorch:deliver` for each epic in turn or that it amends line 7, whichever the user meant. Carrying this to US-1.2 `select` is acceptable.

### Finding F-12: R1.9 is ticked, and no record shows the user confirmed the new wording

Severity: low, non-blocking, because US-1.1 does not use the exception. Owner: coordinator.
Requirement: `tasks.md` R1.9, "confirm the new wording with the user"; `history/review-r1.md` F-9, which asked for the wording to be confirmed because the exception is recorded as the user's decision.
Observed: the narrowing itself is done at `.claude/rules/ohmyorch-delivery.md` line 71, which also gained a sentence on "any required item is absent" Givens. The whole bullet is headed "decided by the user on 2026-11-04". Decision 0002, the work item and the proposal record no confirmation of this wording. Work item line 60 says only that the rerun "absorbs" the sentence. I cannot see the user's messages, so the confirmation may have happened.
Expected: a confirmation that a task claims is recorded, or the wording is marked as the coordinator's pending confirmation.
Consequence: the next story to use the exception would rely on coordinator wording under a user attribution.
Remediation: Coordinator: record in the work item when the user confirmed the wording. If that did not happen, ask before any story relies on the exception, and say so in the work item.

### Finding F-13: the inventory says install paths come from `which -a`, and one does not

Severity: low, non-blocking. Owner: Implementer. Carrying it forward is acceptable.
Requirement: Scenario "Preserve existing work" (accurate record); task 1.2.
Observed: `docs/engineering/prerequisite-inventory.md` line 85 says "Install paths come from `which -a <tool>`". `which -a docker-compose` lists only `/usr/local/bin/docker-compose`, yet line 110 records `/Users/josoroma/.docker/cli-plugins/docker-compose`. The path exists and its version matches, so the recorded value is correct and only the stated source is loose. `history/test-report-r1.md` line 206 noted this and no R1 task picked it up.
Expected: the stated source covers every recorded path.
Consequence: small. A reader reproducing the table with `which -a` finds one row fewer.
Remediation: Implementer: add to line 85 that the Compose plugin path was found by inspecting `~/.docker/cli-plugins`, at the next edit of this file.

## Round 1 findings rechecked

| Finding | Status | Evidence |
|---|---|---|
| F-6 cache rules, blocking | Resolved | `.gitignore` lines 25 to 29; all samples exit 0 and `-v` names those lines. See the criteria table |
| F-7 hygiene account | Resolved | Inventory lines 169 to 172, 184 to 187, 193, 199 and 219 to 232 record what was added, on what authority, and the transcript gap |
| F-1 Supabase network note | Resolved | Inventory lines 128 and 253; plan line 234 replaces "External: none" |
| F-2 "tools in use" | Resolved | Inventory rows at lines 183 to 185 state rule status. "tools in use" is gone from the proposal and inventory. Three rows replace the one the task named, a deviation the work item discloses and harmless |
| F-3 `CODEBASE.md` sentence | Resolved | Inventory line 140 |
| F-8 scripts row | Resolved | Inventory line 148. Re-run: three shebangs with one `version_info` check each; `harness_lib.py` has neither and is imported at `scripts/verify.py` line 15 |
| F-4 protected-paths wording | Resolved | Bridge line 46 removes the plan allowance and requires explicit user authority |
| F-5 exception carried through | Resolved | Decision 0002 line 29 and bridge line 110 |
| F-9 "disposable environment" | Wording resolved; confirmation unrecorded | Bridge line 71. See F-12 |

## Independent checks

**Implementation of `.gitignore`.** Lines 1 to 24 are identical to `34ae38f` (`diff` exit 0). `git diff -U0` shows the five rules each prefixed `+` and no `-` line. The marker is at line 24, and the rules follow in the planned order. `sed -n '25,$p' .gitignore` and `.checks/US-1.1/gitignore-lines.txt` have the same SHA-256, `bc0aea2e…287c`, which confirms the work item's claim that the coordinator wrote them verbatim. The base revision has none of them (`grep -c` prints 0). Beyond the plan's samples, `apps/api/.pytest_cache/x` and `apps/web/.pnpm-store/x` also exit 0, so the rules match at depth. `git ls-files -ci --exclude-standard` prints nothing, and no existing file falls newly under these rules. File times match the plan's order: plan and proposal 17:14:31, `status-before-r1.txt` 17:14:45, `.gitignore` 17:16:34, inventory 17:18:24, capture 17:21:16.

**Inventory probes.** 23 version commands returned the recorded values, and `/opt/homebrew/bin/supabase --version` was run once and printed `2.98.2`. `which -a` for the tools matches the recorded paths apart from F-13. `command -v pnpm` and `which -a pnpm` exit 1. Also matching: base SHA, branches, no remote names, 2 commits, 159 tracked files with per-path counts under both `git ls-tree` and `git ls-files`, all 19 asset paths, link targets, the `python3` alias with 3.15.2 and 3.9.6, 5 hook entries, non-executable scripts, the first record's field names in `research/qwen38-gguf-memory.jsonl`, and the absence of Corepack from tracked files at `34ae38f`. No compatibility verdict appears: the only statuses are "present" and "missing".

**Reconciliation.** Every statement under `Runtime and Tooling` in `CODEBASE.md` has a row at inventory lines 144 to 159, and the results are correct. The line 163 note on the 3.9.6 process matches `CODEBASE.md` line 70.

**Secret safety.** The narrow scan exits 1 on the inventory. A wider scan of 11 shapes over the 11 manifest files, the work item, `goal.md`, `status.md` and the manifest has one hit, in `SPECS.md` line 57, and it is the tail of "risk-policy-and-performance-qualification". No URL appears in these files. The inventory refers to the provider master-key file only in prose, at lines 135, 189 and 257. Nothing in these files was seen to hold a secret.

**Non-overwrite.** `git diff --quiet HEAD -- .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests` exits 0. `git status --short` compared with `status-before-r1.txt` differs only by `.gitignore`. The `.claude/settings.local.json` modification time is 14:52:28, before the story's work began. That comes from metadata only, and a time can be preserved, so it is supporting evidence. The contents were not read.

**Decisions applied as recorded.** Local transcripts: samples exit 1, attributed to OQ-1 at inventory lines 172, 187 and 199, and not raised as a finding. Other caches: seven samples exit 1 and are not raised as findings. A search of the inventory, work item, proposal, plan, Decision 0002, `CODEBASE.md` and `goal.md` finds no claim that every cache is covered. No record says this story established version control. The hygiene scenario was scored from observation, since the Given held.

**Decision records against `AGENTS.md`.** No contradiction found in the bridge rule or Decision 0002. The protected-path procedure keeps writers disjoint and reviewers read-only, and it adds no authority over a guard or acceptance. The exception never scores `PASS` and does not apply to this story. "Delivery targets" keeps the `AGENTS.md` boundaries, and `SPECS.md` holds `External:` lines on US-3.4 and US-7.2, so `promote` cannot lift them. The proposal, plan and Decision 0002 agree on the cache and transcript decisions. The inconsistencies found are F-10 and F-11.

**DH-W05.** The work item says operating behavior is unchanged and references `docs/engineering/runbooks/development-harness.md` with its regression command. Plan line 224 names the section, `Run the delivered checks`, which exists at runbook line 26. Exercising it belongs to the tester, so that part is not evaluated here.

**Task honesty.** All 16 ticks were checked. R1.1 to R1.8 hold. R1.9 is ticked without a recorded confirmation (F-12). Tasks 1.4 and 2.2 keep their round-0 text and ticks, and plan lines 81 and 83 mark them superseded by R1.1, which the plan allows. `SPECS.md` changes only the status row, the story's `Status` and the `Change:` line, and `specs.py validate` exits 0.

**Harness.** I did not run `verify.py`, because this task allows no other file write and it rewrites `.checks/harness/latest.json`. That report is `passed`, with `inputs_unchanged_during_check` true and transport `none`, and was written in the same second as the manifest. A read-only recomputation of `harness_lib.fingerprint` returns `54d7d100…7577`, equal to the report's `input_fingerprint`, so it still covers the current inputs. This is harness evidence only.

**Scope.** `check-scope --plan … --diff .checks/US-1.1/changed.txt` reports IN SCOPE, 11 changed, all predicted, exit 0. As plan line 164 says, this is weak, because any path named in the plan counts as predicted. Reading the 11 files and diffs found nothing outside the plan.

## Acceptance Criteria Evaluated

| Scenario | Result | Evidence |
|---|---|---|
| Preserve existing work | PASS | `docs/engineering/prerequisite-inventory.md` lines 11 to 136 and 234 to 247, re-run as above. `pnpm` is recorded as missing and exits 1. No secret value was found, and tracked settings are unchanged. Limits are listed below |
| Establish repository hygiene | PASS | The Given held: the base revision had none of the five rules. `git check-ignore -q --no-index` now exits 0 for all six cache samples, and for all 13 samples of the other required ignores. Version control is present and predates the story. Name scans of history and of `changed.txt` find no credential, transcript or disposable-data name, apart from the one memory-sample file the inventory explains. Transcripts have no rule and are excused by decision OQ-1, not by observation |

## What could not be checked

- **Whether the user made the recorded decisions:** OQ-1, the cache decisions, protected paths and the exception. Only project records and the coordinator's note say so. The relayed user request in this run does not state them.
- **The story's commit,** which does not exist yet. "Without committing" rests on history and the pending file set, and those scans are limited: a credential or transcript under an unremarkable name would not appear.
- **Secrets outside the scanned shapes.** Pattern scans do not prove absence. I did not check mechanically for the master-key filename, because this task forbids naming it in a command, so that rests on reading the inventory.
- **How real cache tools' output matches the rules.** Only sample paths were probed, because no such tool exists here. The inventory says the same.
- **Non-overwrite of `.claude/settings.local.json`,** beyond the modification time.
- **Implementer process claims that leave no artifact,** and the outbound request itself. The Supabase network note remains an inference from round 1, and I did not repeat the network-denied run.
- **`managed-files.sh` behavior on a plugin upgrade.** Its markers were read, and the replacement was not exercised.
- **Installs outside the search path,** as inventory line 85 discloses.
- **Deliberately left alone:** `.env` files, the provider master-key file, the contents of `.claude/settings.local.json`, the environment, `PATH`, remote URLs, `docker version`, `docker info`, installs and service starts. No hook denied a command, so nothing was left out or rephrased.

## Handoff

To the Tester for independent acceptance of both scenarios and the DH-W05 runbook exercise, on this fingerprint. The coordinator takes F-10 and F-12 into the work item before the evidence review, and records a disposition for F-11 and F-13. This review does not declare the story delivered, and it does not establish H0, H1 or product acceptance.
