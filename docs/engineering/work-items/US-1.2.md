# US-1.2 — H0 shared instructions and development assistant assets

## Plan

Source: [US-1.2](../../../SPECS.md#us-12-h0-shared-instructions-and-development-assistant-assets), SP-001, SP-017, DH-03, DH-04, Decisions 0001 and 0002, SP-020 H0-02, [DH-W01–06](../../PRD/PRD-Development-Harness.md#dh-091-work-item-evidence-contract). Delivered through `/ohmyorch:deliver EPIC-1`, change `us-1-2-h0-shared-instructions-development`.

**Intended behavior:** shared rules link to a check or review responsibility without inconsistent duplication; an unavailable or incompatible assistant adapter reports as explicitly inactive, with no new provider, paid call or activation claim; the read-only ingestor and its paired caller produce a source-traceable proposed backlog on a disposable copy without inventing behavior.

**Invariants:** the real `SPECS.md` is not rewritten by the forward exercise; no model provider, paid call or activation claim; no install, service start or credential read; protected paths are authored by the implementer and persisted verbatim by the coordinator.

**Affected layers, order and verification:** in the change's `implementation-plan.md`, `design.md` and `tasks.md`. An architect critique found 8 blocking gaps in the first draft, and a recheck found 1 more; the planner resolved them before implementation.

**Decisions by the coordinator, not the user, open for the user to overturn** (the plan lists them in full): "each rule" granularity; "incompatible" covering presence, version and configuration validity, with the developer client's model route recorded as not checked; the validation fallback, under which DH-04's "qualified CLI" clause would be reported as not met; the coordinator as the ingestor's paired caller, with the tester scoring; leaving the two `event_delivery_qualification` literals unchanged.

**Decision by the user, 2026-11-05:** the optional-activation scenario is scored from an arranged Given, stating that the condition was arranged and no real adapter was inactive here. Recorded in the bridge rule and Decision 0002 for all stories.

**Deviation at `select`:** the US-1.1 carry-forward edits to `.claude/rules/ohmyorch-delivery.md` and Decision 0002 were uncommitted when this story was selected, by coordinator choice, so they land in this story's commit and its reviewer covers them.

**Rollback:** revert the story commit.

## Implementation

Author: `ohmyorch:implementer`, a separate delegated context, in two passes. 18/18 tasks ticked, four of them R1 remediation tasks: R1.1 by the implementer, R1.2 to R1.4 by the coordinator. Its report is summarized here; its checks are claims until the reviewer and tester repeat them.

**Changed by the implementer:** `scripts/harness_lib.py` (rule-link check, `AGENTS.md` mapping check, qualification allowlist, derived `assistant_adapter`, `reduced_env()`), `scripts/verify.py` (records and prints the adapter status), `tests/harness/test_assistant_assets.py` and `tests/harness/forward_arrangement.py` (new), `docs/engineering/runbooks/development-harness.md`, `docs/engineering/ohmyorch-adaptation.md`, and `tasks.md`. Most went through shell Python, a heredoc or `sed`, in its scope; plugin guards did not see those writes.

**Persisted through the protected-path procedure, 21 edits, authored by the implementer and applied verbatim by the coordinator with the Edit tool:** six `.claude/rules/*.md` files, a links line in `.claude/rules/ohmyorch-delivery.md`, `AGENTS.md` (rule mapping section), `CLAUDE.md` (runbook link, outside the managed block), `.claude/agents/autobots-spec-ingestor.md` (`Change:` line grammar), seven skills under `.claude/skills/` (relevant paths and failure behavior), and, in reopen round 1, `.claude/agents/autobots-architect.md` and `.claude/agents/autobots-nextjs.md` (Return sentences), so 23 edits in all.

**Coordinator changes in this story:** `SPECS.md` status and `Change:` line; `CODEBASE.md` revision; the proposal, plan, design and spec delta as the planner authored them; the bridge rule and Decision 0002 for the carried US-1.1 items; the bridge rule's Records row, reworded by the ruling below; and the two tables in the evidence, copied verbatim.

**Actual behavior:** on the real tree the adapter reads `configured_unqualified` / `delivery_unverified` with CLI 2.1.314 and `model_route: not_checked`. Arranged runs read `inactive` / `unavailable` and `inactive` / `version_below_minimum`. No real adapter was inactive on this machine, and nothing claims activation. `verify.py` pending profiles exit 2.

**Coordinator ruling, not a user decision:** `docs/engineering/option-b-contract.md` line 70 makes a runbook's last-exercised revision, date and result mandatory for a verified claim, which conflicted with the bridge's "does not record it". The contract governs: the runbook links to the story's evidence, and that evidence must state them. SP-018 leans toward the runbook recording them itself, so this is supported for location only and departs from SP-018's literal wording. The bridge applies it to later stories; the user has not confirmed it.

**Deviations reported by the implementer:** task order in pass 1 (2.6 first); `.claude/hooks/dispatch.py` and `.claude/ohmyorch/project.json` copied by name to scratch roots beyond the probe rule's list; mapping row labels shortened; additions beyond the design (`reduced_env()`, allowed links must exist and not be in fences, no "no network" docstring claim); runbook prerequisite wording and two extra recovery rows; task 2.3 says two manifest comparisons where the plan and runbook have one.

**Reopen round 1:** review finding F-1 rejected the result-contract `yes` for `autobots-architect` and the `autobots-nextjs` agent. The coordinator amended the plan to name both as protected paths, and resolved F-2 (user decision above), F-3 (decision 8 in the plan) and F-4 (attributions in Decision 0002 and the bridge rule).

**Reported, not acted on:** `README.md` still links HARNESS-ADAPT-001 as "Evidence"; `PRD-Development-Harness.md` line 123 says `python3 scripts/verify.py`; `claude --version` may reach the network, which is unknown.

## Review

**Reviewed fingerprint (final):** `88121c61d7a9bf19371dae19b8893624865c2438c2170323be84fa05cf97f51b`, 34 files. Verdicts at their archived path: [review.md](../../../openspec/changes/archive/2026-11-05-us-1-2-h0-shared-instructions-development/review.md), [test-report.md](../../../openspec/changes/archive/2026-11-05-us-1-2-h0-shared-instructions-development/test-report.md) and `history/` beside them.

| Round | Reviewer | Result |
|---|---|---|
| Plan | `autobots-architect`, twice | 8 blocking, then 1 blocking, in the draft plan; planner resolved them before implementation |
| 1 | `ohmyorch:reviewer`, fresh context, fingerprint `bdf741ed…` | `changes-requested`, F-1 blocking, F-2 to F-4. Preserved as `history/review-r1.md` |
| 2 | `ohmyorch:reviewer`, fresh context | `pass`, 0 blocking, 2/3 criteria; the ingestion scenario could not be evaluated before the forward exercise |
| Test, adversarial | Three read-only `Explore` lenses (probes, scoring, boundaries) over the verdicts, retained in [adversarial-checks.json](../evidence/US-1.2/adversarial-checks.json) | 9 non-blocking refutations, 2 of them the same `status.md` staleness. No recorded result changed |
| Evidence | `autobots-reviewer`, separate context | First pass: 7 blocking findings, E-1 to E-7. Re-check: 5 resolved, E-4 and E-7 partly, and a new blocking N-A on this row. Second re-check: see the last row of the next table |

| Finding | Disposition |
|---|---|
| Round 1 F-1: two agent result contracts | Fixed through the protected-path procedure; round 2 confirmed |
| Round 1 F-2: arranged Given rested on unconfirmed wording | Put to the user, who confirmed it on 2026-11-05 by choosing "Score from arranged test (Recommended)" on a question stating it as a standing rule |
| Round 1 F-3: Records row is an eighth coordinator decision | Listed as decision 8. Supported for location only, and departs from SP-018's literal wording. **Open for the user** |
| Round 1 F-4: loose attributions | Fixed in Decision 0002 and the bridge rule |
| Round 2 F-1: stale plan and proposal lines | Accepted. In the manifest, so not edited; superseded lines named in the evidence, and the tester was told |
| Round 2 F-2: R1.3's file row | Accepted for the same reason; the decision is recorded above |
| Round 2 F-3: this record | Fixed |
| Round 2 F-4: adaptation page's `final/` sentence predates two agent edits | Accepted. The review's rerun gave the same results, stated in the evidence |
| Adversarial: raw output, forward "no difference", omitted ingestor flag, verification coverage, CLI "qualified" wording, temp directories | Recorded as corrections or reconciliation in the evidence. No conclusion changed |
| Adversarial: Scenario 1 PASS while the common-rules condition was open | Resolved once the summary stated revision, date, result and untested steps. Evidence review confirms |
| Adversarial: `status.md` stale | Refreshed by the coordinator |
| Evidence N-6: scenario 3 is not covered by OpenSpec verification, by the planned ordering | Accepted: the tester covered the scenario, and the evidence discloses this. A stricter reading of the bridge's verify condition is the user's call |
| E-1 to E-3, E-5, E-6: missing or false record items | Fixed in this record and the summary; re-check confirmed |
| E-4: literals, overturn consequence, label mapping | Fixed. The label mapping departs from the plan, by the coordinator's reading, and says so |
| E-7: raw-artifact availability | Fixed, including the negative-control output and the corrected pointer |
| N-A: this table lacked the evidence dispositions | Fixed by these rows |
| N-1, N-4: limits and DH-W04 shape | Limits added to the summary. Accepted as they stand: per-assertion requirement mapping and an expected column were not added (the IDs are per story, and the commands are in the test report); the stub stays listed under both Disposable and Mock; model transport is not its own field, though the evidence states no application model call; the tester's `input_fingerprint` is not in the summary, and the final value is in the manifest |
| N-2, N-3, N-5: unlabelled reading, plan versus bridge scope of the user decision, frontmatter limit | Labelled or stated in the summary |
| N-B to N-F: prompt shaping, wording | Stated or corrected in the summary. Prompt shaping is a real limit on scenario 3, to be reported to the user at the next report |
| Second re-check | E-4 and N-A resolved once this row was added. No blocking finding from this review remains. This row and the non-blocking edits above were not reviewed again |

## Verification

See the [evidence summary](../evidence/US-1.2/summary.md). Harness results are harness evidence only.

## Runbook

[Development harness runbook](../runbooks/development-harness.md), updated by the implementer in this story. Exercise status, including what stays untested, is in the evidence summary.
