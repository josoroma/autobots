---
name: autobots-plan-change
description: Plan one authorized Autobots work item against its SPECS and PRD acceptance requirements, identifying affected layers, contracts, state transitions, verification and recovery before implementation.
---

# Plan a bounded change

Read `.claude/autobots.json`, the mapped contract, selected SPECS story and only its cited sources. Inspect relevant code and CODEBASE as evidence of current behavior. Preserve stable identifiers and distinguish the requested result from tempting adjacent features.

Create or update `docs/engineering/work-items/<work-item-id>.md` under [DH-W01–06](../../../docs/PRD/PRD-Development-Harness.md#dh-091-work-item-evidence-contract). Record:

- Story and requirement IDs, observable acceptance, current behavior and intended change.
- Owned files/layers and interfaces; state/contract compatibility, migration/seed or operational impact.
- Smallest useful checks, their required environment/class, independent review scope and runbook/recovery plan.
- Actual missing decisions, dependencies and risks; identify work that can proceed independently.

Assign disjoint files when delegation helps; use the read-only `autobots-architect` for cross-layer decisions. Keep the plan proportional. Existing authorization permits routine implementation choices; planning adds no approval ritual or permission for services, migrations or paid calls outside the task.

Return the bounded plan, source mapping and any acceptance-blocking gap. H0/H1 remains a prerequisite for product features; a harness-only request does not authorize building the app.
