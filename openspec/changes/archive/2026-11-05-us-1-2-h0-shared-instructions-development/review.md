# Review — us-1-2-h0-shared-instructions-development

Change: us-1-2-h0-shared-instructions-development
Story: US-1.2
Verdict: pass
Blocking: None
Coverage: 2/3 acceptance criteria evaluated
OpenSpec verify: VERIFIED in the checks that ran: 0 critical, 2 warnings (F-1 stale decision text in the proposal and plan, F-4 the adaptation page's `final/` sentence), tasks 18/18, requirements 3/3 located in code and tests, `openspec validate --strict` valid. Scenario Coverage for "Ingest without inventing product behavior" is not verified because the forward exercise runs after review, so readiness for archive is not claimed. Steps followed by hand from the skill text because this agent has no skill-invocation tool.
Reviewed fingerprint: 88121c61d7a9bf19371dae19b8893624865c2438c2170323be84fa05cf97f51b

Reviewer: `ohmyorch:reviewer`, a fresh delegated context separate from the implementer, the coordinator and the round 1 reviewer. Evidence is static reading or a re-run local probe, with model transport none. `story_manifest.py compare US-1.2` passed before the review, on 34 files.

## Summary

The implementation satisfies the two scenarios that can be evaluated now, and no finding blocks. The round 1 blocking gap is closed: both agents' result contracts now name what DH-04 requires, and the two sentences match the text the implementer authored. "Separate optional assistant activation" passes on arranged conditions only, and no real adapter was inactive on this machine. "Ingest without inventing product behavior" could not be evaluated, because the forward exercise has not run. Four non-blocking record findings go to the coordinator. The most important is F-1: the plan and proposal still say Decision 2 rests on an unconfirmed sentence, which contradicts the new user confirmation, and I could not see that confirmation myself.

## Findings

No finding below blocks. None makes acceptance false or breaches a boundary, and none needs the implementer.

### Finding F-1: records of the 2026-11-05 decision contradict each other, and the confirmation cannot be seen from this review

Severity: non-blocking. Owner: coordinator.
Requirement: `proposal.md` Open Questions says `implementation-plan.md` lists each decision and who made it. The plan's "Evidence summary must state" list binds what the summary reports.
Observed: four records say the user confirmed it: `.claude/rules/ohmyorch-delivery.md` line 75, Decision 0002 line 45, `docs/engineering/work-items/US-1.2.md` line 15 and plan line 38. These still say otherwise:
- Plan line 35: the coordinator "decided all seven", "none is a user ruling".
- Plan line 255: decision 2 "rests on the coordinator's unconfirmed bridge sentence". The tester reads this row.
- Plan line 440: the evidence summary must state "Decision 2's reliance on the bridge sentence marked 'Coordinator's wording, not put to the user'". That is now false. The sentence with that label is now "merely hard to run", which is a different sentence.
- Plan lines 439, 483 and 492, and `proposal.md` line 92, repeat "seven" or "none was put to the user".
- `proposal.md` line 59 points to the same relabelled sentence.

Separately, the only user voice in this task's context is the relayed request, which does not mention the decision, and the coordinator's note carries no user authority. No record quotes the user's words, unlike the "Delivery targets" bullet. The records also differ on what was confirmed: the work item and plan name this scenario, and the bridge and Decision 0002 state a general rule for all stories. I therefore report the confirmation as recorded, not as verified.
Expected: every record agrees on who decided what, and the evidence summary is not told to state something false.
Consequence: the tester or the summary could report a superseded reliance. The score does not change, because the behavior was observed either way and the bridge's arranged-precondition clause covers this scenario as written.
Remediation: put the correction in the tester's delegation prompt and in the evidence summary, naming plan lines 255 and 440 as superseded. Add the user's actual words to the work item. Do not edit the plan or proposal now, because they are in the manifest and the bridge sends any such edit after capture through the reopen route. If another reopen happens, correct them then.

### Finding F-2: task R1.3 is ticked but only partly done, and decision 8 is recorded less durably than the rule it changes

Severity: non-blocking. Owner: coordinator.
Requirement: `tasks.md` R1.3: list the Records-row ruling in the plan's Settled decisions "and row 125". Round 1 expected the ruling to name SP-018.
Observed: decision 8 is at plan line 44 and names SP-018. The file row, now plan line 128, still says only "One added line of links, on top of the coordinator's existing F-12 edit". It mentions neither the Records row nor the 2026-11-05 split. Plan line 137 says "No further change expected" for Decision 0002, which round 1 changed. Review Scope at line 455 names neither. `docs/engineering/work-items/US-1.2.md` line 33 cites only contract line 70 and says "The contract governs", without SP-018. The summary and final report it also lists cannot exist yet.

On support: the reading holds for location, because a runbook final at capture cannot state an exercise that happens after capture, and DH-W05 says "link their evidence". SP-018 says "Record its last successful exercise and link evidence", which plainly reads as the runbook doing both, so this departs from its literal wording rather than merely leaning. Bridge line 35 states the reading as a standing rule for every later story, with no "coordinator's" label, although its neighbouring bullets now carry such labels. The only provenance sits in this change's plan and work item.
Expected: the tick matches the work, and a coordinator reading that binds later stories is labelled where it binds them.
Consequence: a later story will read the bridge's row as settled. Nothing in US-1.2's acceptance changes.
Remediation: name SP-018 in the work item, and ask the user to confirm decision 8 in the final report because it outlives this story. On the next reopen or the next bridge edit, label the row and update plan lines 128 and 137. The evidence review must still confirm the summary states revision, date and result and lists untested steps, or the common-rules table's last row reads `no`.

### Finding F-3: the work item does not record the two agent files as persisted through the procedure

Severity: low, non-blocking. Owner: coordinator.
Requirement: bridge Protected paths step 3: the coordinator "records in the Implementation section which paths were persisted this way".
Observed: `docs/engineering/work-items/US-1.2.md` line 27 lists 21 edits and neither agent file. Line 37 says the plan was amended to name them but not that they were persisted this way. Line 23 still says 14/14 tasks, and the tree has 18/18. The edits themselves are correct: both new sentences contain the exact strings in `.checks/US-1.2/protected/edits_r1.py`.
Expected: the Implementation section names both paths and the procedure.
Consequence: the record understates what the procedure covered. No code is affected.
Remediation: add one sentence naming `.claude/agents/autobots-architect.md` and `.claude/agents/autobots-nextjs.md`, and update the task count. The work item is a record, so this needs no reopen.

### Finding F-4: the adaptation page's `final/` sentence predates the two agent edits

Severity: low, non-blocking. Owner: coordinator for the record, tester for the rerun.
Requirement: plan line 228, "rerun on the final tree's copies", and task 2.4's check that the recorded result matches the control.
Observed: `docs/engineering/ohmyorch-adaptation.md`, under "CLI control", says each pair ran again under `final/` "on copies taken after" the rule, skill and agent edits. `diff -rq` shows `.checks/US-1.2/validate-control/final/plugin-good/agents` differs from `.claude/agents` in the two round 1 files. Round 1's own run, `protected/r1-plugin-good.json`, covered a good copy only. This review reran both pairs on current copies under `.checks/US-1.2/review/r2/cli/` with the same results, so the recorded outcome still holds.
Expected: the recorded control covers the final tree.
Consequence: the sentence is slightly stale, and the conclusion is unaffected. Agents appear only in the good copies, and the page says so.
Remediation: state in the evidence summary that both pairs were rerun on the final tree, citing this review or a tester rerun. Change the page only on another reopen.

## Acceptance Criteria Evaluated

| Scenario | Result | Evidence |
|---|---|---|
| Keep development policy portable | PASS | `config_errors` empty on the real tree; 8 rule files linked and each link apt for its layer under DH-09; `AGENTS.md` line 38 mapping has a row per section plus settings and `CLAUDE.md`; both tables repeated below. One row is conditional: "Runbook exercise status" holds only once the evidence summary exists, and the evidence review must confirm it |
| Separate optional assistant activation | PASS | Arranged conditions only; no real adapter was inactive on this machine. `PATH=/usr/bin:/bin` reads `inactive`/`unavailable`. A stub at 2.1.200 reads `inactive`/`version_below_minimum` and records only `--version`. The real tree reads `configured_unqualified`/`delivery_unverified`, `model_route: not_checked`. Scans and the unchanged block are clean. Scored under the arranged-precondition clause recorded as the user's; see F-1 |
| Ingest without inventing product behavior | UNVERIFIED | Not evaluable at review: the forward exercise has not run, so no ingestor output exists to read. Static parts hold: ingestor lines 16 and 18 and its read-only tools, the paired-skill and fixture tests, and an arranged copy that validates with the fixed statuses. The loaded ingestor definition is unproven |

## Round 1 findings, checked

| Finding | State | Basis |
|---|---|---|
| F-1, agent result contracts | Resolved | Both Return sentences now name the invariants, restated from the same file's duties (architect line 14, Next.js line 12), and the architect adds source evidence for each. No tool or behavior added. Text matches `edits_r1.py`, both paths are named in plan lines 120 and 121, and both left the `git diff --quiet` block. The table rows are updated |
| F-2, Decision 2's authority | Resolved in the bridge, Decision 0002, work item and plan line 38. Not resolved everywhere | See F-1. The confirmation is recorded, not verified here |
| F-3, eighth decision | Partly resolved | Plan line 44 lists it and names SP-018. See F-2 |
| F-4, attributions | Resolved | Decision 0002 line 38 reads "except where marked", line 47 marks the reading as the coordinator's, line 45 and bridge line 76 agree that "merely hard to run" is unconfirmed |

## Checks repeated

| Check | Result |
|---|---|
| Scope, `check-scope --plan ... --diff .checks/US-1.2/changed.txt` | IN SCOPE, 34 of 34 predicted. Naming a path makes it predicted, so the block below is the real check |
| `changed.txt` against the manifest's keys and `git status` | Equal to the keys. `git status` adds only records that `is_record` excludes |
| Expected-unchanged `git diff --quiet` block | Exit 0 |
| `test_assistant_assets.py` alone; all of `tests/harness`; all under `PATH=/usr/bin:/bin` | 53 OK; 122 OK; 122 OK |
| `specs.py validate`; retained fixture; arranged copy | PASS: 42 stories; 4 stories; 4 stories |
| Stale navigation on a copy | Exit 1, then `render` and `validate` exit 0 |
| Arrangement refusals | Existing destination and outside `.checks`: exit 2 each |
| `verify.py --profile` fast, full, db, operations | Exit 2, `not_implemented`, each |
| Provider and `claude -p` scans | No hit in either |
| Pin and source hash | Checkout, `upstream.commit`, the install SHA and the page agree; the ingestor hash matches the page |
| Qualification values | `not_tested` and `not_qualified_one_pretooluse_event_observed`, unchanged |
| `grep -c 'Last exercised'` on the runbook; old fragment `evidence-and-last-exercise` | 0; no reference |
| Activation wording in added instruction, runbook and page text | Three hits: a denial in `CLAUDE.md`, DH-04's "qualified CLI" clause quoted in the page, and the two-state explanation. Nothing reads as activated or qualified |
| Protected files | `edits.py` (21 edits) and `edits_r1.py` (2 edits) all present in the tree. Against scratch `run-2`, only the two agents and the bridge differ, and the bridge differs only in the Records row and the 2026-11-05 split, both disclosed as the coordinator's records |
| Base ingestor hash; first-pass failures of the two real-tree tests | Hash equals `HEAD`; failures present in `asset-tests-real.txt` |
| `validate-implementation-plan`; plugin doctor | 0 failures, 0 warnings; no failing check |
| Links in changed documents, two tables and the work item | 376 checked. The only unresolved ones are the two expected links to the evidence summary |

Task ticks: each ticked task has matching code, tests or records, except R1.3 (F-2). R1.2's tick rests on the recorded confirmation (F-1).

## Ruling on task 2.6

**Pair 2 counts, confirmed independently, not reused.** On fresh copies of the current tree under `.checks/US-1.2/review/r2/cli/`, with CLI 2.1.314:

| Pair | Good copy | Broken copy |
|---|---|---|
| `.claude` shape, `--json` | Exit 0, `success: true`, empty `contents` | Exit 0, `success: true`, warning on `description`. Does not count |
| Plugin shape, `--strict --json` | Exit 0, `success: true`, empty `contents` | Exit 1, `success: false`, the only `contents` entry names the file and path `description` |

`diff -r` shows the copies differ by the one line. The CLI's help says `--strict` means "Treat warnings as errors (exit 1)". So the failure has one cause and its report names the fault, and DH-04's clause is met within these limits. Decision 4's fallback does not apply. The page's claim about the name-only manifest also holds in the saved `minimal-manifest` output.

Limits, sharper than round 1 recorded:
- A skill frontmatter `name: [unclosed` passes the CLI under `--strict` with no finding, while an unterminated quote gives an `errors` entry on `frontmatter`. So the CLI catches some malformed YAML, not all.
- An unknown skill key (`bogus-key`) and a `name` not matching the directory pass with no finding.
- An agent with no description fails under `--strict`.
- The harness frontmatter test catches the name faults and unknown keys, so they stay on it. Rules are not covered by the CLI.
- "Qualified" means only the recorded 2.1.314, above DH-05's 2.1.295.

## DH-04 table, repeated

I read all 20 files. Every cell in `docs/engineering/evidence/US-1.2/dh-04-table.md` holds. Added relevant paths match each rule's `paths`, and the two skills with no rule use DH-03's record paths. The failure-behavior lines restate existing text and add no behavior.

| Weakest judgment | Ruling |
|---|---|
| `autobots-architect`, result contract | Accepted: invariants and source evidence are now named |
| `autobots-nextjs` agent, result contract | Accepted: invariants are named, with commands and results as evidence |
| `autobots-reviewer`, result contract | Accepted, marginal, confirmed on my own reading. The file says only "inspected scope", which alone would fall short by the standard used on the two agents above. It holds because `autobots-review-change`, which delegates to it, requires "inspected invariants". The two rejected agents had no such pairing |
| `autobots-plan-change`, failure behavior | Accepted, thin: it returns "any acceptance-blocking gap" and records missing decisions |

I could not confirm that the table was persisted verbatim, because the implementer's returned text is not available to me.

## Common-rules table, repeated

I read the copies directly on the current tree, rather than relying on the table. Every row reads yes, with no contradiction among authored assets. `docs/engineering/evidence/US-1.2/common-rules-table.md` is dated before reopen round 1, so it is not literally the final-tree run. The round 1 edits to the bridge, Decision 0002 and two agents change no compared rule.

| Row | Note |
|---|---|
| Profile availability, Interpreter, OpenRouter-only, Document map, Upstream pin, Ingestion ownership, Evidence locations | Yes. `PRD-Development-Harness.md` line 123's `python3` stays a source discrepancy |
| No automatic actions in hooks | Yes. The dispatcher uses only `report_state`, and no hook runs the version probe |
| Review independence | Yes. "Read-only" in `delivery.md` and `autobots-implement-item` against a verdict-writing reviewer is the closest reading, and Decision 0002 settles it as two roles |
| Plugin stance | Yes, through Decision 0002's supersession and the page's banner |
| Story field order | Yes. `specs.py` has no `Change:` rule and tolerates the line as prose, and the ingestor now names it |
| Runbook exercise status | Conditional, as the table says. See F-2. `README.md` still links HARNESS-ADAPT-001 as "Evidence", without calling it current, which the work item reports |

## Coordinator decisions

Decision 2 is recorded as the user's (F-1). The others remain the coordinator's, none is a user ruling, and each stays open.

| Decision | Assessment |
|---|---|
| 1. "Each rule" granularity | Supported. H0.2 says "rules link". Profiles are pending, so review is what applies today, and `AGENTS.md` says so |
| 3. "Incompatible" | Narrower than the sources. DH-01 speaks of a "compatible assistant route". Defensible, because checking would need files `AGENTS.md` puts out of bounds and the field carries `model_route: not_checked`. The scenario's "incompatible" is exercised for version and configuration only, which the final report should say |
| 4. CLI fallback | Moot under the ruling above. The fallback itself has no source, as the plan admits |
| 5. Coordinator as paired caller | Supported by the scenario's actors and the bridge's "the coordinator does not test" |
| 6. Literals unchanged | Supported. The scenario forbids a new claim |
| 7. Carried edits | A disclosed departure from the bridge's start-of-goal "must", with no source permitting it. Its purpose is met, because review covers the edits |
| 8. Records row | Supported for location only. It departs from SP-018's literal wording and binds later stories. See F-2 |

Carried edits: F-11 and F-12 are resolved. Decision 0002 line 47 quotes "loop delivery one epic by epic until complete all", which matches the relayed request, and marks the reading as the coordinator's. The "any required item" ruling agrees in bridge line 74 and Decision 0002 line 44. The research-payload ruling is in Decision 0002 line 46, which says it is recorded there and not in the bridge.

## Handoff

Tester for acceptance, after the coordinator runs the forward exercise as the plan orders. No implementer work is needed. The coordinator should carry F-1's correction in the tester's prompt, and F-2 to F-4 into the records and final report.

Not checked:
- Ingestion scenario, as above.
- Live event delivery, and whether rules load in a live session. The project instructions attached to this review context are an older text than the reviewed files: they have no mapping section, runbook link or managed block. So a session can hold stale definitions, which is the risk the plan names for the ingestor.
- The developer client's model route, and whether `claude --version` reaches the network.
- A full `verify.py` run under arranged `PATH`, which would overwrite the report. I called the status helper directly instead, and the tester runs it in full.
- The user's words for the 2026-11-05 decision, and the evidence summary, which does not exist yet.

No hook denied a command. Scratch went to `.checks/US-1.2/review/r2/`. The test suite also creates and removes its own temporary directories, under `.checks` and in the system temporary location, which could not be avoided while running it.
