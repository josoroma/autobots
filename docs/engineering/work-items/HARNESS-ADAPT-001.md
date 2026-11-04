# HARNESS-ADAPT-001 — source-traceable specification harness

## Plan

Source: [Decision 0001](../decisions/0001-ohmyorch-adaptation.md), [SP-001–003](../option-b-contract.md), [DH-W01–06](../../../PRD-Development-Harness.md).

Clone and pin OhMyOrch; adapt the ingestor and authoring workflow locally; retain existing SP decisions; regenerate SPECS into bounded source-traceable stories and generated views. Add focused development skills/agents/rules, deterministic project hook scripts and an independently usable verification command. Do not build the app, install dependencies, start services or call models.

Verify with positive/negative parser and hook fixtures, source/link checks, navigation idempotence, unavailable-profile behavior and an independent review/forward exercise. Document and exercise the actual local runbook. Record implementation limits, especially live assistant delivery and outstanding H0/H1 gates.

## Implemented

Cloned and pinned the requested source; retained its provenance without installing/executing the plugin. Preserved all 21 SP requirements in the engineering contract and regenerated SPECS as 10 epics, 42 stories and 84 tasks with mechanically derived navigation.

Added shared instructions, 13 project skills, seven agents, seven rules, mapped configuration, five command-hook event handlers, the backlog parser/renderer and the portable harness checker. Initialized the local Git repository and ignores without adding or committing files. No developer model/provider settings were changed.

The baseline uses the existing `/opt/homebrew/bin/python3.12` because an independent process resolved plain `python3` to unsupported macOS Python 3.9.6. Scripts now reject unsupported interpreters clearly. Full application tooling, Supabase/worker fixtures, live assistant delivery and provider qualification remain pending; the unavailable verification profiles fail explicitly.

## Review

`/root/nextjs_research` independently reviewed the root-owned dispatcher, verifier and fingerprint/report logic. Findings about incomplete reports, empty hooks, mapped-source omissions and disabled/asynchronous hooks were fixed with negative fixtures. `/root/langchain_research` reviewed the assistant assets; the epic heading level, summary placement and dependency/source grammar were corrected to match the parser. The coordinator reviewed integration, source coverage and the renderer's limited mutation scope.

`/root/ingest_forward_test` used the actual ingestion workflow on a disposable fixture. It preserved missing retry policy and contradictory cancellation requirements, did not promote prototype behavior to intent, wrote only fixture SPECS and produced no delivery claims. Its interpreter failure exposed the PATH issue, which was corrected rather than hidden. The durable evidence retains the fixture and result.

## Verification

The delivered harness has 45 behavioral tests: 33 parser and 12 hook/report/configuration tests. Skill frontmatter validation passed for all 13 skills. See the [durable manifest and observed results](../evidence/HARNESS-ADAPT-001/summary.md) for final input fingerprints, command results, reviewer scope and retained artifacts. The runbook exercises validation, navigation idempotence, the harness profile and explicit unavailable-profile/unsupported-interpreter behavior.

This completes the bounded adaptation request, not all H0/H1 stories. The initial backlog deliberately makes no DONE claim; broader acceptance includes toolchain, database and application checks not supplied by this subset. No application, Docker or live inference success is claimed.

## Runbook

[Development harness runbook](../runbooks/development-harness.md) documents actual commands, expected outcomes, limits and failure/recovery. The evidence record identifies the exercised revision. Bulky raw reports stay in ignored `.checks`; reviewed summaries and synthetic fixture artifacts remain versioned.
