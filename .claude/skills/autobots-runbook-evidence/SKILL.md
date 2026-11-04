---
name: autobots-runbook-evidence
description: Maintain and exercise an Autobots work item's reproducible runbook and redacted evidence record on its authorized target, distinguishing tested procedures from templates and unrun instructions.
---

# Make the result reproducible

Read `.claude/autobots.json`, the mapped contract, work record and relevant harness/deployment procedure. Use [DH-W04–06](../../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract) as the completion contract.

Create or update `docs/engineering/runbooks/<runbook-id>.md` with prerequisites, exact target identity, real commands, expected checkpoints, recovery and cleanup. Inspect scripts before documenting their invocation. If operating behavior is unchanged, say so and link the existing verified procedure plus relevant regression command; do not invent an operational change.

Exercise applicable in-scope steps and a meaningful failure/recovery path. This skill does not itself authorize persistent mutation: only explicitly requested operational work may invoke guarded migration, seed, reset, restore or service lifecycle scripts. Never run such work implicitly, from an edit hook, or against an unverified target. Reuse existing authorization without asking again.

Record actual source/config/lock/verifier fingerprints, tool versions, exact redacted commands, expected/observed assertions, exits, failures/skips, date and environment. Separate static/mock/disposable/live evidence and `none`/`mock`/`openrouter_live` transport. An unexercised procedure remains unverified.

Version the reviewed manifest and summary in `docs/engineering/evidence/<work-item-id>/`, linking the independent review and runbook. Keep bulky raw artifacts in ignored `.checks/<work-item-id>/<evidence-id>/` with hashes, availability and retention. The durable summary must stand on its own after raw logs expire. Exclude secrets, user content and unredacted transcripts.

Return the exercised steps/results, recovery result, durable links and exact limits. Templates and handwritten passing labels cannot close a work item.
