# Verification — us-9-3-qualified-upgrades-checkpoint-compatible

Change: us-9-3-qualified-upgrades-checkpoint-compatible
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `8cba043`, working tree with this change. Target: a disposable Compose project with a scripted model. No paid call, real credential or persistent stack.

Commands: `python3.12 scripts/qualify_upgrade.py` (41 cases, exit 0, 51 s), `scripts/qualify_backup.py` (45), `scripts/qualify_operations.py` (70), `scripts/qualify_identity.py` (242), `scripts/verify.py --profile fast`, `--profile harness`.

## Scenarios

**Preserve execution semantics during upgrade: observed, images unchanged.** The prior release's own code and 24 migrations, read from `8cba043`, wrote a finished run, a paused run with real checkpoints and a queued job. The images are the same in both releases, so only application and schema changed.
- New code on the old schema: `schema_behind`, admission 503, and a new worker claimed nothing.
- A failing migration rolled back with no partial table (arranged), an edited applied migration was refused (arranged), then this release applied forward, readiness returned, and all checkpoints remained.
- Bindings hashed the same before and after the upgrade. Saved runs got a contract marked `upgrade`.
- A worker on another model, with the workspace default changed: `paused`, `route_not_bound`, no call, binding unchanged. Resumed on its original model, the prior queued job succeeded.
- A prior checkpoint, after owner reconciliation and an arranged resume (no usable key for the route), continued to success on this code with no repeated effect.
- Blocked honestly (arranged contract edits, a changed tool and an unreadable graph state): `paused`, `incompatible_version` recorded, no model built, no call, no checkpoint. Cancelled by the owner, then a linked new run recorded the current contract. The resume route's reason was checked through its function, not the route, as no usable key exists.

**Qualify adapter migrations: observed for the installed release, a changed one arranged.** No other release was installed. The adapter's own `setup()` in a scratch schema matched all migration-owned columns, its 10 migrations were recorded, the saver resolved to `agent_runtime`, no checkpoint table in `public`, and the runtime role was denied creating a table, altering one and qualifying an adapter. Arranged: an extra adapter step changed both the schema comparison and the identity; with no qualification recorded, Operations said `adapter_unqualified`, admission gave 503 and a real worker left the job queued; recording it restored readiness.

## Found and fixed while verifying

- Tracing-off only ran at process entry. A process skipping that, with arranged host settings, tried to reach the arranged `.invalid` collector, so nothing left this machine. It's now enforced at agent construction too, langsmith's cache is cleared, and a case covers it.
- `route_not_bound` used to fail a saved run for good. It now pauses it. Stop reasons recorded before a run's first segment used to be lost, and are now kept.

## Limits

- Harness success is harness evidence only. This doesn't establish H1 or product acceptance.
- Not observed: a real image change, a real framework release, a persistent upgrade (no guarded persistent apply exists), a controlled checkpoint migration (none exists or is needed yet), or resume through its route.
- `PRIOR_REVISION` needs this branch's history. A squash would break the qualifier until it's repointed.
- The `operations` verify profile is still reported as not implemented, by the repository's contract. The three qualifiers exist, and wiring them in is a small follow-up.
