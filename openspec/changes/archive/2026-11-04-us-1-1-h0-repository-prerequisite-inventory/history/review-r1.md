# Review — us-1-1-h0-repository-prerequisite-inventory

Change: us-1-1-h0-repository-prerequisite-inventory
Story: US-1.1
Verdict: changes-requested
Blocking: 1 finding(s)
Coverage: 2/2 acceptance criteria evaluated
OpenSpec verify: MISMATCH: 1 critical, requirement not implemented: Repository hygiene (`.gitignore` lacks the five cache rules DH-03 requires). Tasks 7/7; `openspec validate --strict` valid; Design Adherence unchecked (no design.md, intentionally absent per plan). Steps followed by hand from the skill text because this agent has no skill-invocation tool. Readiness for archive is not claimed.
Reviewed fingerprint: 69df0ac2b649fe796d6b48a534faa42e6135ede6311fbf3b7e48d2526acbdbb8

Reviewer: `ohmyorch:reviewer`, a delegated context separate from the implementer and coordinator. `python3.12 scripts/story_manifest.py compare US-1.1` printed `PASS: compare: US-1.1: 10 files match the reviewed manifest` before this rewrite, so the reviewed inputs are unchanged. All evidence here is static or a re-run local probe, with model transport none.

**This rewrite replaces an earlier version of this file**, for the same fingerprint, whose verdict was `pass` with no blocking findings and coverage 1/2. That version held the cache question open instead of scoring it. The facts were already visible then, and they support a blocking finding on their own, as F-6 sets out. The coordinator directed this rewrite and reported the user's decision. F-1 to F-5 keep their IDs.

## Summary

The inventory satisfies "Scenario: Preserve existing work". Every recorded value re-run here matched, `pnpm` is correctly the missing prerequisite, no secret value or remote URL was found, and the document makes no compatibility verdict.

"Scenario: Establish repository hygiene" fails. DH-03 requires ignoring caches without limiting that to tools in use, and five cache categories have no rule. So the Given is met, and the Then, "ignores are established", is false. The Implementer followed the plan here: the defect comes from a scoping call in the proposal and plan, not from implementer conduct.

There is one blocking finding and eight non-blocking ones.

## Findings

**Ownership.** The Owner line routes each finding.
- **Implementer:** `docs/engineering/prerequisite-inventory.md`. `check-write-scope` returns ALLOW.
- **Protected-path procedure:** `.gitignore`. `check-write-scope` returns BLOCKED for the implementer, so it goes through bridge rule lines 39-46: the plan names it, the implementer authors the content, and the coordinator writes it verbatim.
- **Coordinator:** `.claude/rules/ohmyorch-delivery.md` (BLOCKED for the implementer), Decision 0002, and the persisted `openspec/` planning artifacts.
- **One correction to the routing note:** Decision 0002 is not mechanically protected. `check-write-scope --role ohmyorch:implementer` returns ALLOW for it. It is coordinator-owned because it is a decision record, not because a guard stops the implementer.

### Finding F-6: required cache ignores are absent, so the hygiene scenario's Then is unsatisfied

Severity: blocking. Owner: `.gitignore` through the protected-path procedure; planning artifacts and the decision record through the coordinator.
Requirement: Scenario "Establish repository hygiene"; `PRD-Development-Harness.md` line 71 "Ignore `.claude/settings.local.json`, local transcripts, bulky `.checks` outputs, caches and disposable data"; SP-001 item 1 "Establish repository ignores and version control if absent".
Observed: `git check-ignore -q --no-index` exits 1 for `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo` and `.pnpm-store/x`. `.gitignore` has no matching rule, its only cache rule being `__pycache__/` at line 8, and it is unchanged from `HEAD`. Inventory line 181 records "No rule exists". Proposal lines 29 and 74 and plan lines 87 and 155 exclude these categories as not yet in use, which DH-03 does not say. `.gitignore` does carry rules for `.venv/`, `node_modules/` and `.next/`, also not in use, so the repository applies no such limit either. The deferral has no carrier in the target story: the US-1.3 acceptance and tasks in `SPECS.md` never mention ignores, and these five names appear in no story. Bridge rule line 24, "A story that adds tooling adds its ignores", is a general coordinator instruction, not US-1.3 acceptance, and it cannot satisfy DH-03 in this story. With a required ignore absent, the Given is met. By the plan's own line 167, "If the probes show the Given does hold, the exception does not apply".
Expected: where required ignores are absent, preparing the foundation establishes them, preparing only what is missing. The work item at line 58 records a user decision on 2026-11-04 to add these rules in this story. This review cannot confirm that decision directly, but the finding does not depend on it. Local transcripts stay as the user decided, with no rule, and are not a finding.
Consequence: the first `pytest`, `ruff`, `mypy`, `tsc` or `pnpm` run leaves untracked, non-ignored output. `story_manifest.py` then binds it and `compare` fails, or it gets committed. None of these paths exists today, so nothing is exposed now.
Remediation: Protected-path procedure for `.gitignore`: add exactly `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo` and `.pnpm-store/`, outside the `# OHMYORCH:BEGIN ignores` managed block, with no transcript rule. Verify that each sample exits 0, that every other recorded sample keeps its exit code, and that `git ls-files -ci --exclude-standard` lists nothing (no tracked file matches these patterns today). Coordinator: persist a revised proposal (lines 14, 29, 74, 83), plan (lines 87, 144, 155, 163, 167, naming `.gitignore` as a protected path as bridge rule line 41 requires) and tasks, and record the decision in Decision 0002 beside line 42.

### Finding F-7: the inventory's hygiene account omits the cache call and will become false

Severity: medium, non-blocking alone but required with F-6. Owner: Implementer.
Requirement: Scenario "Preserve existing work" (accurate record); task 2.2 "record that in the inventory".
Observed: `docs/engineering/prerequisite-inventory.md` line 208 says "With OQ-1 applied, nothing is missing for this story to prepare". OQ-1 covers transcripts only, so the sentence already skips the five categories its own line 181 shows without a rule. Once F-6 is resolved, four more statements turn false: "This story established nothing" (line 169), "No rule exists" (line 181), "no ignore rule was added or changed" and the `git diff --quiet HEAD -- .gitignore` result (line 208), and the overwrite check naming `.gitignore` (lines 216-219), which will exit 1.
Expected: the section states what was missing, what was added and on what authority.
Remediation: Implementer: rewrite lines 169, 181, 208 and 216-219 to record the five rules as added under the user's decision and transcripts as still ruleless by OQ-1, and replace the `.gitignore` overwrite check with one showing that only those rules were added.

### Finding F-1: the inventory omits that `supabase --version` contacts the network

Severity: low, non-blocking. Owner: Implementer; the plan line through the coordinator.
Requirement: Scenario "Preserve existing work"; the plan's Dependencies line "External: none" (`implementation-plan.md` line 183); task 1.2's reproducible probes.
Observed: `docs/engineering/prerequisite-inventory.md` line 128 records only an "update notice". Lines 227-229 tell the reader to re-run the probes and give no network warning. Under `sandbox-exec` with network denied, `/opt/homebrew/bin/supabase --version` printed `2.98.2`, exit 0, with no notice. Run normally, it printed the v3.0.0 notice. That points to a live outbound check rather than a cached result. This is inference from behavior, not a packet capture.
Expected: a reproduction record states what its probes do.
Consequence: each re-run, including the Tester's, makes an undisclosed outbound request. No secret or project data was seen to be involved, and no source forbids it, so this is not a boundary breach.
Remediation: Implementer: state at line 128 and in `Reproducing this inventory` that this probe makes an outbound update check. Coordinator: correct "External: none" in the revised plan.

### Finding F-2: the hygiene row "Caches, for tools in use" names tools that are not in use

Severity: low, non-blocking. Owner: Implementer; the proposal's wording through the coordinator.
Requirement: Scenario "Preserve existing work" (accurate record); task 2.1's item-by-item Given evaluation.
Observed: `docs/engineering/prerequisite-inventory.md` line 180 places `.venv/x`, `node_modules/x` and `.next/x` under "tools in use", and proposal line 29 is the origin. `test -e` exits 1 for `.venv`, `node_modules`, `.next`, `package.json` and `pyproject.toml`, and `CODEBASE.md` line 52 says there is no application. The split between lines 180 and 181 actually tracks "has a rule" versus "has no rule".
Expected: labels that describe the observed state. Only `__pycache__` and `.DS_Store` are demonstrably in use.
Consequence: a reader takes "in use" as a principle that was applied, which is the reasoning behind F-6.
Remediation: Implementer: replace the two row labels with one that states the observed rule status. Coordinator: drop "for tools in use" from the revised proposal.

### Finding F-3: the inventory says `CODEBASE.md` "was not edited"

Severity: low, non-blocking. Owner: Implementer.
Requirement: Scenario "Preserve existing work" (accurate record); task 1.3 "Do not edit `CODEBASE.md`".
Observed: `docs/engineering/prerequisite-inventory.md` line 140 says "`CODEBASE.md` was not edited". The same changed set edits it: `git diff` shows a new revision, a new note and a pointer to this inventory at `CODEBASE.md` line 16. `.checks/US-1.1/status-before.txt` shows it was already modified before implementation, and the implementer's scope excludes it, so the implementer's own conduct looks right.
Expected: a sentence that is true as read.
Consequence: the committed record contradicts the commit that contains it.
Remediation: Implementer: scope the sentence, for example "This comparison edited nothing; the coordinator owns `CODEBASE.md`".

### Finding F-8: the reconciliation row on scripts generalizes past `scripts/harness_lib.py`

Severity: low, non-blocking. Owner: Implementer.
Requirement: Scenario "Preserve existing work" (accurate record); task 1.3.
Observed: `docs/engineering/prerequisite-inventory.md` line 148 says of "the scripts" that "their `#!/usr/bin/env python3` line resolves to Python 3.15.2" and "They check for 3.12 or later". That holds for `specs.py`, `story_manifest.py` and `verify.py`, each with a shebang and one `version_info` check. `scripts/harness_lib.py`, which line 77 lists among the scripts, has neither: it starts with a docstring and is imported by `scripts/verify.py` line 15. The earlier version of this review called this row accurate, and that was too generous.
Expected: the row distinguishes the three entry points from the imported module.
Consequence: small. The row's conclusion stands, since the module runs under whichever interpreter `verify.py` was started with, but its literal claim about all four files is false.
Remediation: Implementer: name the three entry points at line 148 and say that `harness_lib.py` is an imported module with no shebang or version check of its own.

### Finding F-4: the protected-paths rule implies a plan can change a guard or a story's acceptance

Severity: medium, non-blocking, because the rule's wording does not itself change any acceptance. Fix it before F-6 uses the procedure. Owner: coordinator.
Requirement: `AGENTS.md` "Preserve source requirements" and "Do not infer new requirements from code"; `references/contract.md` "Human decisions and approved source documents govern intent".
Observed: `.claude/rules/ohmyorch-delivery.md` line 46 reads "Never use it to change a guard, a hook registration's protection or a story's acceptance without saying so in the plan". The planner is a read-only specialist, so this wording makes a plan statement sufficient to alter acceptance. It also conflicts with line 3 of the same file, "Never patch the pinned upstream checkout or bypass a guard". Decision 0002 line 40 has the opposite framing, "The upstream guard is unchanged".
Expected: changing a story's acceptance or a guard requires a recorded human decision, not a line in a plan.
Consequence: F-6 and then US-1.2 and US-1.4 use this procedure, and a plan could narrow acceptance while appearing to follow the rule.
Remediation: Coordinator: limit the "say so in the plan" allowance at line 46 to hook registrations a story must legitimately change, and require a recorded user decision for acceptance or a guard.

### Finding F-5: the unmet-Given exception is not carried through to two statements it qualifies

Severity: low, non-blocking. Lowered from low to medium, because after F-6 US-1.1 no longer relies on the exception for its hygiene scenario. Owner: coordinator.
Requirement: DH-W06 "required checks have current passing evidence"; `AGENTS.md` completion evidence.
Observed: `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md` line 29 still requires "full verified coverage" before `archive`, while line 41 of the same file adds the exception. `.claude/rules/ohmyorch-delivery.md` line 110 says "A delivered story means its acceptance has current evidence", which would not be true of any story archived under the exception.
Expected: the exception does not claim a scenario passed, so it does not directly contradict `AGENTS.md`, but the statements about what "delivered" means should match it.
Consequence: a later "delivered" report under the exception overstates what has evidence.
Remediation: Coordinator: qualify Decision 0002 line 29 and bridge rule line 110 so each names the exception and requires the report to state which scenario went unexercised.

### Finding F-9: the bridge rule's "disposable environment" sentence is overbroad

Severity: low to medium, non-blocking. Owner: coordinator, with the wording confirmed by the user because the exception is recorded as the user's decision.
Requirement: `.claude/rules/ohmyorch-delivery.md` line 71, the unmet-Given exception.
Observed: line 71 gives "Given X is absent" as the qualifying example, then ends "A precondition that could be arranged in a disposable environment, or a scenario merely hard to run, does not qualify". A scratch directory can arrange almost any absence, so read literally the last sentence cancels the exception it closes. `implementation-plan.md` line 165 gives a sound reason for having no fixture, that a run "would exercise only commands written for the test", but the sentence does not state that condition. The earlier version of this review raised this as an open question, and work item line 53 now answers it the same way.
Expected: a sentence that separates what it means to exclude from what the exception allows.
Consequence: the next story to use the exception cannot tell whether it qualifies, and a tester reading it literally would refuse every use.
Remediation: Coordinator: narrow the sentence to preconditions whose arrangement would exercise behavior the story actually implements, and confirm the new wording with the user.

## Scoring: the hygiene scenario

The exception is not the route for this scenario, because its Given is met. Re-run results:

| Item | Probe result | Basis |
|---|---|---|
| Version control | `true`, exit 0 | Observation: not absent |
| `.env`, `.env.local`, `.claude/settings.local.json`, `.checks/x`, `*.log` and disposable data samples | Exit 0 for each | Observation: not absent |
| Local transcripts: `transcript.jsonl`, `transcripts/x.md`, `.claude/projects/x.jsonl` | Exit 1 for each | No rule, recorded as not missing by user decision OQ-1. Not a finding |
| Caches: `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo`, `.pnpm-store/x` | **Exit 1 for each** | **Absent. DH-03 requires them, and no decision excuses them.** See F-6 |

After remediation, the Tester scores what it finds on the probes, attributing the transcript gap to OQ-1, and the earlier `UNVERIFIED` expectation at `implementation-plan.md` line 167 no longer applies. The existing `test-report.md` predates this verdict and does not cover the remediation.

## Independent checks

**1. Probes.** All 24 tool version commands in the table returned the recorded value. `which -a` for all 14 tools matched the recorded path sets, and pnpm exits 1 under both `which -a` and `command -v`. Also re-run and matching: branch, no remotes, 2 commits, 159 tracked files with the per-path counts, `ls ~/.nvm/versions/node/`, all link targets, shebangs, the `python3` alias with 3.15.2 and 3.9.6, 5 hook entries, non-executable scripts, and every sample under `git check-ignore`. Each of the 19 asset paths exists. A check of common locations outside the search path found no `pnpm`, so that result stands. No compatibility verdict appears; "present" and "missing" are the only tool statuses.

Not defects, and within the limit line 85 states:
- `/Users/josoroma/.hermes/node/bin/corepack` exists outside the search path and is not listed.
- `shasum`, `awk`, `sed`, `grep`, `find` and `mktemp`, which `doctor` also checks, are not in the table. Task 1.2 did not list them.

**2. Secret safety.** No secret value or remote URL was found in the 10 manifest files, the work item, `goal.md`, `status.md` or the manifest. The work item was scanned before its later additions, so that one result is older than the rest:
- The narrow scan exits 1 on the inventory.
- A wider scan covered cloud and platform token shapes, JWT, private-key headers, assignments, URL credentials and `git@`. Its three hits are false positives: the inventory's own regex literal (line 215), the plan's copy (line 128), and base-revision text in `SPECS.md` line 57 containing "risk-policy".
- No URL appears in these files, and `git remote` prints nothing.
- Long-token listing shows only paths and identifiers.
- The master-key filename, extracted from the PRD by script and not printed, has zero matches in the changed files. The inventory uses prose only.
- `.checks/US-1.1/` holds no environment-style or key-shaped lines.
- Home paths are not secrets (A3), and base-revision evidence already contains them.
- The `.claude/settings.local.json` modification time is 14:52, before `status-before.txt` at 15:52, so it shows no write during implementation. Only `stat` was used, the contents were not read, and a modification time can be preserved, so this is supporting evidence only.

**3. Hygiene wording.** At this fingerprint, line 169 states "This story established nothing" and that the When and Then were not exercised. Line 183 attributes "not missing" to the user decision and says "Not a probe result", and lines 188-190 state the gap. Nothing implies establishment. Line 181 reports the missing cache rules honestly. Line 208 does not carry that through, see F-7.

**4. Reconciliation.** Repeated statement by statement against `CODEBASE.md` lines 25-29. The rows at inventory lines 144-159 are correct and none is missing, apart from the generalization in F-8. Inventory line 161 is also correct that the section does not mention Git, npm or Corepack. `CODEBASE.md` line 27 keeps the imprecise wording, as the plan allows, for a later refresh. A small related point: line 7 says the file describes `34ae38f`, while line 16 names a file not in that revision.

**5. Disclosed deviations.** None was out of bounds.

| Deviation | Judgment |
|---|---|
| Extra probes | In bounds. All read-only, none reads a secret-bearing file. `test -e .claude/settings.local.json` only checks existence and is disclosed at inventory line 134, and the proposal did the same. Results that the inventory relies on are recorded; the second `research/` file is disclosed only in the work item, and nothing depends on it |
| `supabase --version` network call | In bounds, because no source prohibits it, but the plan's "External: none" does not strictly hold, and the behavior is now better evidenced. The work item is honest. The inventory is incomplete, see F-1 |
| Master-key filename in tool output | In bounds. The name comes from a tracked PRD and is not a secret value, and the implementer's account says the file was not touched. The inventory correctly omits the name and says "not probed". The tool output itself could not be inspected |
| Refused out-of-project write | Not a bypass. The guard stops a write; the stdin comparison writes nothing, and `.checks/US-1.1/reverify.txt` shows its output. The plan's "do not rephrase" rule concerns denied probes, not this. The refusal itself could not be observed |
| Sections written in one pass | Harmless. File times show the checks ran last |

**6. Coordinator edits.** `SPECS.md` changes only the US-1.1 table row to `IN PROGRESS`, the story's `Status`, and the new `Change:` line. No task or other story changed, and `specs.py validate` passes. `CODEBASE.md` has the revision, note and pointer, matching bridge line 15. The bridge's list of protected paths matches `check-write-scope.sh` line 28. Contradictions are F-4, F-5 and F-9. None of these edits changes a boundary in `AGENTS.md`.

**Task honesty.** Six ticked tasks hold. Task 2.2 was ticked in line with the plan, which told the Implementer to record no change, but its outcome is wrong under F-6. It was not an optimistic tick. `status-before.txt` compared with `status-after.txt` differs only by the inventory. `git diff --quiet HEAD -- .gitignore .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests` exits 0. `python3.12 scripts/verify.py --profile harness` exits 0, as harness evidence only.

**Scope.** `check-scope --diff .checks/US-1.1/changed.txt` reports IN SCOPE, 10 changed, all predicted. As the plan says, this is weak, because any path it names counts as predicted. Reading the 10 files found nothing outside the plan.

## Acceptance Criteria Evaluated

| Scenario | Result | Evidence |
|---|---|---|
| Preserve existing work | PASS | `docs/engineering/prerequisite-inventory.md` lines 11-136 and 210-223, re-run per checks 1, 2 and 4. Accuracy findings F-1, F-2, F-3 and F-8 do not touch a recorded path, version or missing prerequisite |
| Establish repository hygiene | FAIL | `git check-ignore -q --no-index` exits 1 for all five cache samples; `.gitignore` has no such rule; `PRD-Development-Harness.md` line 71. See F-6 |

## What could not be checked

- Whether the user made the decisions the records attribute to them: OQ-1, protected paths, the exception and adding these rules in this story. Only the records and the coordinator's messages say so.
- The tester's report and the three adversarial checks, which were not reviewed. F-6 to F-9 rest on the probes and reading done here.
- The implementer's process claims that leave no artifact: the refused write, the filename in tool output and that the master-key file was not touched. Assistant transcripts were not read.
- The absence of a secret outside the scanned shapes. Pattern scans covered 14 files and do not prove absence. Reading covered the changed content of those files: for `SPECS.md` and `CODEBASE.md` the diff and the relevant sections, not every line of the base text.
- Whether other version probes contact the network. Only `supabase` was tested. `docker --version` and `docker compose version` gave the same output with `DOCKER_HOST` pointing at a nonexistent socket, so neither needs the engine.
- Tool installs outside the search path, beyond the common locations listed above.
- The Docker engine, `.env` files, the master-key file and the contents of `.claude/settings.local.json`, all deliberately left alone. No hook denied any command in this review.
- `/opt/homebrew/bin/supabase --version` was run three times here, one of them with network denied, so this review probably made the same outbound request twice. `verify.py` also refreshed the ignored `.checks/harness/latest.json`.

## Handoff

Back to remediation, not to the Tester: `delivery reopen`, then the routes in each finding's Owner line, then a fresh capture, review and test. F-6 is blocking. F-1 to F-5 and F-7 to F-9 can be taken up in the same round, and F-7 must be. Acceptance testing does not proceed on this fingerprint.
