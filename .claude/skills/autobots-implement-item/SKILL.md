---
name: autobots-implement-item
description: Implement an authorized, bounded Autobots story from its plan and record actual behavior, changed contracts, deviations and verification handoff. Use after scope and acceptance are defined.
---

# Implement the selected item

Relevant paths: `docs/engineering/work-items/<id>.md`, `docs/engineering/evidence/<id>/` and `docs/engineering/runbooks/<id>.md`.

Read `.claude/autobots.json`, the mapped contract, selected story and its existing work record. Load the domain skill for the files being changed, not every PRD. If no plan exists, establish the concise DH-W01 record first.

1. Inspect current code and preserve unrelated changes. Own explicit files; coordinate shared contracts, migration numbering and generated outputs before parallel edits.
2. Implement the source-supported behavior with the smallest coherent change. Keep Option B's Python lifecycle authoritative; Next.js remains UI/BFF. Never fill an unknown product decision with an undocumented requirement.
3. Add or reuse meaningful checks for changed behavior and failure boundaries. Do not lower gates or delete failing tests to manufacture completion. Run only prepared, in-scope tooling; package installation, services and live model calls are separate operations.
4. Update the work record with actual paths/symbols, resulting behavior, contract/schema/config changes and material deviations. Label stubs and deferred work explicitly.
5. Hand the final diff and relevant evidence to an independent read-only reviewer. Revalidate affected checks after repairs; the coordinator, not a writer, owns status closure.

Return implemented behavior, checks actually run, failures/skips, unresolved acceptance and the review/runbook handoff. Code presence is not verified or live-qualified behavior. Use [DH-W02–06](../../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract) for completion.
