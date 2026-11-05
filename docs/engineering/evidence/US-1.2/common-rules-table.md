# US-1.2 common-rules table

Authored by `ohmyorch:implementer`, persisted verbatim by the coordinator. The final-tree run, by inspection. Every row reads yes. Files unchanged since the first run were not reread line by line: the reading relies on that first run plus `git diff --quiet` or `git status`. Changed copies were reread or checked against the applied edits.

| Common rule | Copies read | Consistent |
|---|---|---|
| Profile availability | AGENTS.md, .claude/rules/delivery.md, autobots-verify-change, .claude/autobots.json, scripts/verify.py, the runbook, README.md | yes. Rules name a profile without restating availability, and the AGENTS.md mapping says pending profiles exit 2. Observed exit 2 for all four |
| Interpreter | AGENTS.md, .claude/settings.json, .claude/autobots.json, the runbook | yes. The runbook uses `/opt/homebrew/bin/python3.12` only where `PATH` is reduced. **Source discrepancy, reported and not edited:** PRD-Development-Harness.md line 123 says `python3 scripts/verify.py` |
| OpenRouter-only and no new provider | AGENTS.md, .claude/rules/model-gateway.md, autobots-model-gateway, CLAUDE.md | yes. The added failure line says no fallback to another model or provider |
| No automatic actions in hooks | AGENTS.md, .claude/rules/delivery.md, autobots-docker-local, .claude/hooks/dispatch.py | yes. The dispatcher imports only `report_state`, so no hook runs the version probe |
| Review independence and record ownership | AGENTS.md, .claude/rules/delivery.md, .claude/rules/ohmyorch-delivery.md, autobots-review-change, autobots-reviewer, the CLAUDE.md managed block, autobots-implement-item, autobots-plan-change | yes. `ohmyorch:reviewer` writes only `review.md`, and `autobots-reviewer` returns findings: two named roles, per Decision 0002. The new bridge line names both. Closest reading: "read-only" review in delivery.md and autobots-implement-item against a verdict-writing reviewer. No file says one role both may and may not write, and delivery.md routes loop delivery to the bridge |
| Document map | .claude/autobots.json, .claude/ohmyorch/project.json | yes, also tested |
| Upstream pin | .claude/autobots.json, autobots-spec-ingest, autobots-spec-ingestor, docs/engineering/ohmyorch-adaptation.md, CODEBASE.md | yes. The first three are tested. The page matches `rev-parse` |
| Plugin stance | Decisions 0001 and 0002, the adaptation page, CLAUDE.md, autobots-spec-ingest | yes, given 0002's supersession note and the page's banner. The page now marks `upstream.json`'s no-plugin sentence as historical |
| Ingestion ownership | CLAUDE.md, autobots-spec-ingest, autobots-spec-ingestor, the runbook | yes. The runbook states the `render` and `validate` split as specific to the exercise |
| Story field order | autobots-spec-ingestor, scripts/specs.py | yes. It read `no` on the first run. Task 1.5's edit lands it, and the test passes |
| Evidence locations | AGENTS.md, .claude/rules/delivery.md, autobots-verify-change, autobots-runbook-evidence, DH-09.2 | yes |
| Runbook exercise status | docs/engineering/option-b-contract.md line 70, .claude/rules/ohmyorch-delivery.md Records row as reworded, the runbook's "Evidence and exercise status" section, DH-W05 | yes, **on the coordinator's reading, not a user decision:** the contract requires the last-exercised revision, date and result for a verified claim. The runbook states they are recorded in the story's evidence and links there. This row holds only once the coordinator records those facts in the summary, and the evidence review must confirm that |
