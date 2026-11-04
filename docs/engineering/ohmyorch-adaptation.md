# OhMyOrch provenance and adaptation

This page covers the spec-ingestor adaptation from Decision 0001. Epic delivery now uses the real plugin; [Decision 0002](decisions/0002-ohmyorch-delivery-loop.md) supersedes the plugin, OpenSpec and continuation exclusions below and lists how the two systems are bridged.

Source: [josoroma/OhMyOrch spec-ingestor](https://github.com/josoroma/OhMyOrch/blob/fddfbf53c8c10d45782796cc9a7edf95bc8d3a07/plugins/ohmyorch/agents/spec-ingestor.md). The requested repository was shallow-cloned to `research/upstream/OhMyOrch` and pinned to commit `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. The checkout is ignored by Git. The ingestion adaptation does not execute its code; since Decision 0002 the delivery plugin runs from it.

## Preserved behavior

- Read product sources before decomposition; CODEBASE is descriptive evidence only.
- Return source-traceable epics/stories with Given/When/Then acceptance.
- Keep IDs stable and distinguish READY, NEEDS CLARIFICATION, BLOCKED, IN PROGRESS and DONE.
- Preserve source conflicts and unanswered decisions rather than inventing product behavior.
- Derive the table of contents, status table and dependency diagrams from story bodies.
- Let the coordinator persist the ingestor's proposed content and own delivery status.

## Adapted for Autobots

| Upstream design | Project adaptation |
|---|---|
| Plugin document map and `${CLAUDE_PLUGIN_ROOT}` | `.claude/autobots.json` maps the actual project documents; no plugin-root dependency |
| Read-only ingestor includes Bash | Project ingestor has Read/Grep/Glob only; caller runs validation and writes output |
| Plugin `doctor`, shell/JQ implementation | Standalone Python backlog tools and repository verification, independent of Claude |
| Plugin OpenSpec/archive/continuation workflow | Existing DH-W plan/implementation/review/verification/runbook evidence contract |
| Existing prose specification | SP-001–021 retained in the mapped engineering contract; EPIC/US backlog adds actionable decomposition |
| Legacy partial/unverified acceptance caveat | Required checks remain unpassed until actual evidence exists; static/mock results never qualify live behavior |
| Plugin distribution/update behavior | Project-local reviewed skills, agents, rules and command-hook settings; no plugin install/update action |

No upstream application model choice, additional paid service, global Claude setting or automatic continuation loop was imported. The clone itself is not an application dependency. Repository metadata at the inspected revision did not include a root license file; this project retains provenance and authors project-specific instructions/scripts rather than redistributing the upstream plugin package.

## Qualification boundary

The local parser checks syntax, source locations, identity, dependency/status consistency and generated navigation. Independent source review is still needed: a valid link does not prove acceptance is supported by the source. Hook script fixtures do not prove actual assistant event delivery. The qualified local runbook and evidence record distinguish these claims explicitly.
