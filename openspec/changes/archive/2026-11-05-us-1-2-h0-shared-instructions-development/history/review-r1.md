# Review — us-1-2-h0-shared-instructions-development

Change: us-1-2-h0-shared-instructions-development
Story: US-1.2
Verdict: changes-requested
Blocking: 1 finding(s)
Coverage: 2/3 acceptance criteria evaluated
OpenSpec verify: VERIFIED in the checks that ran: 0 critical, 1 warning (design D6, the same gap as F-1), tasks 14/14, requirements 3/3 located in code and tests, `openspec validate --strict` valid. Scenario Coverage for "Ingest without inventing product behavior" is not verified because the forward exercise runs after review, so readiness for archive is not claimed. Steps followed by hand from the skill text because this agent has no skill-invocation tool.
Reviewed fingerprint: bdf741ed768a8baed21cf7ca8742c1972f9414432eed55cd94608368aad3438e

Reviewer: `ohmyorch:reviewer`, a fresh delegated context separate from the implementer and coordinator. Evidence is static reading or a re-run local probe, with model transport none. `story_manifest.py compare US-1.2` passed before the review, on 32 files.

## Summary

The code, tests, rule links, `AGENTS.md` mapping, adapter status, activation refusal, ingestor grammar, runbook and adaptation page do what the plan and specification ask, and every implementer claim re-run here held. One gap blocks: two agents' result contracts do not name DH-04's "invariants checked", and the architect's does not name evidence, so the table's `yes` in those cells does not survive a repeat, and the plan's "no unresolved gap" check fails. "Separate optional assistant activation" behaves correctly on arranged conditions, but its `PASS` label rests on a sentence the user has not confirmed (F-2). The ingestion scenario could not be evaluated yet.

## Findings

### Finding F-1: two agent result contracts omit DH-04 elements

Severity: blocking. Owner: implementer authors, coordinator writes, because both files are protected.
Requirement: DH-04, "a concise result contract: findings with paths, invariants checked, evidence, remaining uncertainty". `proposal.md` commits to closing the gaps the per-file table finds. Plan decision 1 makes that table the coverage for agents under "Keep development policy portable", and the plan's Test Strategy row expects "One row per file; no unresolved gap".
Observed: `.claude/agents/autobots-architect.md` line 16 returns requirement mapping, recommended changes with owned paths, alternatives, required checks and open decisions. It names no invariants checked and no evidence. The table's basis maps "invariants" to duties in the paragraph before the Return clause, which a caller is not promised to receive. `.claude/agents/autobots-nextjs.md` line 16 names paths, behavior, commands and results, and gaps, but no invariants checked. The table's basis, "contract impacts", is not that: the agent's session, credential and sanitization invariants on line 12 are never returned. The other five agents have an element a caller can read this way (assertions, ownership, guarantees demonstrated, inspected scope, preserved IDs).
Expected: each agent's result contract names all four DH-04 elements, in any words a caller can act on. The spec wins over a defensible reading.
Consequence: the `yes` cells in `docs/engineering/evidence/US-1.2/dh-04-table.md` for these two agents are overstated, and a caller can get a result with no statement of what was checked. No rule or test is wrong.
Remediation: Amend the plan to name both files as protected paths and take them out of the `git diff --quiet` block, as plan line 151 requires. The implementer then authors one clause in each Return sentence, restating duties already in that file: for the architect, the invariants checked and the source evidence for each; for the Next.js agent, the boundary invariants checked. Add no behavior or tool. The coordinator writes them verbatim, the table is repeated for the two rows, and capture runs again. The plan's risk row sends a gap found at review to this reopen route.

### Finding F-2: Decision 2 scores "Separate optional assistant activation" on a sentence the user has not confirmed

Severity: non-blocking here, because the code and tests do not change either way. It should reach the user before the tester's score stands. Owner: coordinator.
Requirement: the bridge's user-decided clause, `.claude/rules/ohmyorch-delivery.md` line 73: a conditional Given that "does not hold today is scored `UNVERIFIED`, never `PASS`". Decision 0002 line 41 says the same with no carve-out.
Observed: the only support for `PASS` from an arranged Given is line 75, labelled "Coordinator's wording, not put to the user". Plan decision 2 says US-1.2 is the first story to rely on it. US-1.1's review F-12 remediation (`review.md` line 54 in the archived change) said to ask "before any story relies on the exception". That condition has now arrived, and the plan says the question was not put. The bridge's Stopping section routes a decision the sources do not make to `delivery block --reason`.
Expected: an authority for the label that is not the coordinator's own sentence. The plain words support two readings: a stub is a truly incompatible adapter, so the Given holds in the arrangement; or the Given does not hold "today" on this machine, so the row is `UNVERIFIED`. This review does not choose between them.
Remediation: Coordinator: put line 75 to the user, or use the `delivery block` route, before the tester's row is relied on for archive. If the user rejects it, the row becomes `UNVERIFIED` under the exception and the records name the scenario unexercised. The tester should state the reliance in the row whichever way it runs.

### Finding F-3: the Records-row ruling is an eighth coordinator decision, absent from the plan's seven

Severity: non-blocking. Owner: coordinator.
Requirement: `proposal.md` Open Questions says `implementation-plan.md` lists each decision. Option B contract line 70 says a runbook's last-exercised revision, date and result are mandatory for a verified claim, and unexercised procedures remain marked unverified. SP-018 (contract line 244) says each runbook should "Record its last successful exercise and link evidence". DH-W05 says "link their evidence" and "Untested instructions are explicitly untested".
Observed: the work item records the ruling, and `.claude/rules/ohmyorch-delivery.md` line 35 carries it. It is the only difference between that file and the implementer's scratch copy. But the plan's row for that file (line 125), its Review Scope (line 452) and its list of what the evidence summary must state (line 436) do not mention it. The ruling cites line 70 only. Line 70 and DH-W05 do not fix where the facts live, and a final-at-capture runbook cannot state an exercise that happens after capture, so the reading holds for location. SP-018 leans toward the runbook itself recording them and was not weighed. The runbook marks no procedure as untested except live event delivery, and sends the reader to a summary that does not exist yet. `common-rules-table.md` says "Every row reads yes", yet its last row holds "only once the coordinator records those facts".
Expected: the ruling is reported as a coordinator decision with the seven, and it names SP-018.
Remediation: Coordinator: list it in the plan's Settled decisions and row 125 during F-1's amendment, and in the evidence summary and final report. The evidence review must confirm that the summary states revision, date and result and lists untested steps. If it does not, the last table row reads `no`.

### Finding F-4: two attributions in the carried records are loose

Severity: low, non-blocking. Owner: coordinator.
Requirement: the plan's Review Scope for F-11 and F-12, and US-1.1's work item line 64, which names only the "disposable environment" sentence as not put to the user.
Observed: Decision 0002 line 38 heads its list "All by the user", while line 46 correctly says the coordinator reads the user's words as naming every epic. Bridge line 75 puts "a scenario merely hard to run does not qualify" under the coordinator's label too, and no record says whether that clause was the user's. It stood under the user-decided heading before US-1.1's R1.9.
Expected: the heading matches the bullet, and the label matches the record.
Remediation: Coordinator: change the heading to except that reading, and record whether the "merely hard to run" clause was the user's or also unconfirmed. Treating it as unconfirmed is the safe direction, so nothing else depends on this.

## Acceptance Criteria Evaluated

| Scenario | Result | Evidence |
|---|---|---|
| Keep development policy portable | FAIL | Only through F-1, the DH-04 table that decision 1 makes this scenario's coverage for agents. The rule-link and common-rule clauses pass: `scripts/harness_lib.py` lines 280 and 294, `config_errors` empty on the real tree, 8 rule files linked, `AGENTS.md` line 38, and both tables below |
| Separate optional assistant activation | PASS | On arranged conditions only; no real adapter was inactive on this machine. Label subject to F-2. `PATH=/usr/bin:/bin` reads `inactive`/`unavailable`; a stub at 2.1.200 reads `inactive`/`version_below_minimum` and records only `--version`. The real tree reads `configured_unqualified`/`delivery_unverified`, `model_route: not_checked`. Plan scans and the unchanged block are clean |
| Ingest without inventing product behavior | UNVERIFIED | Not evaluable at review: the forward exercise has not run. Static parts hold: ingestor lines 16 and 18, read-only tools, paired-skill and fixture tests, arrangement validates with the fixed statuses. The loaded ingestor definition is unproven in this session |

## Checks repeated

| Check | Result |
|---|---|
| Scope, `check-scope --plan ... --diff .checks/US-1.2/changed.txt` | IN SCOPE, 32 of 32 predicted. Naming a path makes it predicted, so the plan's `git diff --quiet` block is the real check: exit 0 |
| `tests/harness`, `test_assistant_assets.py` alone | 53 tests OK |
| All of `tests/harness`, normal and under `PATH=/usr/bin:/bin` | 122 tests OK in both |
| `specs.py validate`; retained fixture; arranged copy | PASS: 42 stories; 4 stories; 4 stories |
| `verify.py --profile` fast, full, db, operations | Exit 2, `not_implemented`, each |
| Provider and `claude -p` scans | No hit in either |
| Pinned commit and source hash on the adaptation page | Match `rev-parse` and `shasum` |
| Protected files against the implementer's scratch `protected/run-2` | Byte-identical, except the coordinator's Records row, which is disclosed. 21 edits counted in the diff |
| Base ingestor hash; first-pass failures of the two real-tree tests | Hash equals `HEAD`; failures present in `asset-tests-real.txt` |
| Implementer's shell writes | All paths are allowed by `check-write-scope.sh`, so no guard was bypassed |
| Scratch roots | No `settings.local.json` or `.env*` by name under `.checks/US-1.2` |

Links in changed documents: the only unresolved ones are the two expected links to the evidence summary, in the runbook and adaptation page. Task ticks: each ticked task has matching code, tests or records, except that 1.7 and 1.8 inherit F-1's over-generous cells, which was a judgment openly flagged rather than a false claim.

## Ruling on task 2.6

**Pair 2 counts.** The `--strict` failure, with the fault in `warnings` and `errors` empty, is the broken copy's error naming the fault. DH-04's "validate frontmatter against the qualified CLI" clause is therefore reported as met within the limits below, not as not met, and decision 4's fallback does not apply.

- The CLI's own help says `--strict` means "Treat warnings as errors (exit 1)", and design D7 stated that before the run.
- `diff -r` shows the copies differ by the one `description` line. The manifest has no findings. The only item in `contents` names the file, path `description` and "No description in frontmatter". So `success: false` has one cause. Re-run here on the `final/` copies: exit 0 and exit 1. Those copies equal the current tree under `diff -r`.
- Added probes under `.checks/US-1.2/review/cli/`: malformed YAML gives a true `errors` entry on path `frontmatter`, exit 1. An agent with no description gives a warning, exit 1 under `--strict`.

Limits: an unknown skill key and a skill `name` not matching its directory both pass the CLI with no finding, so those stay on the harness frontmatter test. Rules are not covered. The `LICENSE_MISSING` `blocking: true` entry under `directory` appears in the good copies too and did not affect `success`, because no `--profile` was given. The runs used scratch copies. "Qualified" means only the recorded 2.1.314, which is above DH-05's 2.1.295.

## DH-04 table, repeated

All 13 skill rows and every cell read as the table says, except the two result-contract cells in F-1. Added relevant paths match each rule's `paths`, and the two skills with no rule use DH-03's record paths. The failure-behavior lines restate existing text and add no behavior; "do not install a dependency to get past it" matches the skill's own "checks must not silently sync or install" and DH-09.

| Weakest judgment | Ruling |
|---|---|
| `autobots-architect`, result contract | Rejected, F-1 |
| `autobots-nextjs` agent, result contract | Rejected, F-1 |
| `autobots-plan-change`, failure behavior | Accepted, thin: it returns "any acceptance-blocking gap" and records missing decisions rather than inventing them |
| Not listed as weak: `autobots-reviewer`, result contract | Accepted, marginal: "inspected scope", with `autobots-review-change` requiring "inspected invariants". It could take the same clause during F-1 |

## Common-rules table, repeated

Every row reads yes on the final tree, with no contradiction among authored assets. Read directly rather than relying on the first run, except that `README.md` was read in part (lines 1-20 and 32, plus a search), and `dispatch.py` by its imports and `report_state` use.

| Row | Note |
|---|---|
| Profile availability, Interpreter, OpenRouter-only, Document map, Upstream pin, Ingestion ownership, Evidence locations | Yes. `PRD-Development-Harness.md` line 123's `python3` stays a source discrepancy |
| No automatic actions in hooks | Yes. The dispatcher imports only `report_state`, so no hook runs the version probe |
| Review independence | Yes. Closest reading is "read-only" in `delivery.md` and `autobots-implement-item` against a verdict-writing reviewer. Decision 0002 settles that as two roles |
| Plugin stance | Yes, through 0002's supersession and the page's banner |
| Story field order | Yes. `specs.py` has no `Change:` rule and tolerates the line as prose, and the ingestor now names it |
| Runbook exercise status | Conditional, see F-3 |

## Coordinator decisions

None of the seven is a user ruling. On support in the sources:

| Decision | Assessment |
|---|---|
| 1. "Each rule" granularity | Supported. H0.2 says "rules link", and the links are apt for each layer under DH-09's profiles. Profiles are pending, so review is what applies today, and `AGENTS.md` says so |
| 2. Scoring from an arranged Given | **Not supported by any user-confirmed source.** See F-2 |
| 3. "Incompatible" | Narrower than the sources. DH-01 speaks of a "compatible assistant route" and SP-002 of not assuming model IDs work in that CLI, so a route-incompatible client reads `configured_unqualified`, not `inactive`. Defensible, because checking would need files `AGENTS.md` puts out of bounds, and the field claims nothing and carries `model_route: not_checked`. The scenario's "incompatible" is exercised for version and configuration only |
| 4. CLI fallback | Moot under the ruling above. The fallback itself has no source, as the plan admits |
| 5. Coordinator as paired caller | Supported by the scenario's actors and the bridge's "the coordinator does not test" |
| 6. Literals unchanged | Supported. The scenario forbids a new claim, and the evidence must say they are not a full list |
| 7. Carried edits | A disclosed departure from the bridge's start-of-goal "must", with no source permitting it. The purpose is met, because this review covers the edits |

Carried edits: F-11 and F-12 are resolved as US-1.1's records describe, apart from F-4. The "any required item" ruling agrees in the bridge, Decision 0002 and US-1.1's work item, and the research-payload ruling agrees in the last two. Decision 2's statement that Decision 0002 has no carve-out is accurate. The relayed user words match the F-11 quotation.

## Handoff

Implementer for F-1 remediation through the reopen route, after the coordinator amends the plan, then capture, review and test again. F-2 goes to the coordinator for the user. F-3 and F-4 are coordinator records.

Not checked: live event delivery, whether rules load in a live session, the developer client's model route, a full `verify.py` run under arranged `PATH`, which would overwrite the report (the status was read directly, with the implementer's saved outputs agreeing), and whether `claude --version` reaches the network. No hook denied a command. Scratch went to `.checks/US-1.2/review/`. The test suite also creates and removes its own temporary directories under `.checks`, which could not be avoided while running it.
