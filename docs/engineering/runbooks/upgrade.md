# Runbook: upgrades and forward recovery

Moving to a new application, schema, Supabase or framework release without changing what saved runs mean.

**Last exercised:** `python3.12 scripts/qualify_upgrade.py`, on a disposable project, writing `.checks/upgrade/qualification.json`. It starts from a prior release's own code and migrations (`PRIOR_REVISION` in the script, read from git history) with a scripted model. Images and pinned packages are the same in both releases, so an image change was **not** observed, and an adapter change was arranged. On the real install, on 2026-11-06, it was followed for one real migration, [as US-11.3 records](../../../openspec/changes/archive/2026-11-06-us-11-3-guarded-persistent-install-exercised/verification.md).

## What's protected

- **Bindings:** the model, role policy, Expert version and session on a saved run never change. A migration doesn't touch them, and a worker on another model pauses the run with `route_not_bound`.
- **Semantics:** each run records its graph state and tool versions. A run this release can't honor pauses with `incompatible_version` before any model or checkpoint, and resume answers 409. The owner can cancel it and start a linked new run, which records the current contract.
- **Framework:** the installed checkpoint adapter has an identity, from its version, migrations and SQL. If no migration has recorded it as qualified, Operations says `adapter_unqualified`, no job is claimed and admission answers 503.

## Changing a tool or graph state

In `domain/execution.py`: raise the version. Old runs then stop at `incompatible_version`. Only if old checkpoints keep their exact meaning, list the change in `COMPATIBLE_TOOL_CHANGES` or `COMPATIBLE_GRAPH_STATES`, and have a person review that entry. A controlled checkpoint migration, if one is ever needed, has to be written and qualified for that change. None exists.

## Upgrade procedure

1. Read the new migrations, and any change in `infra/supabase`, `uv.lock` or adapter version.
2. Drain, stop and back up as in [the operations runbook](operations.md) and [the backup runbook](backup-restore.md).
3. Restore that backup to an isolated instance and try the upgrade there first, with `services/agent/.venv/bin/python scripts/persistent_install.py apply --project "$RESTORED_PROJECT" --restored-copy`. That needs the copy's matching identity and its restore hold still in place. Physical backups restore only with the Compose files and images they were taken with, so restore from the old revision, then upgrade.
4. Apply migrations to the install with `services/agent/.venv/bin/python scripts/persistent_install.py apply --project autobots-install`. For a disposable target it's `scripts/app_db.py`.
5. Start the API. `schema_behind` means migrations are still missing, and nothing is admitted. Start workers once it's ready.

**Not exercised on the install:** `schema_behind`, as its one migration only changed a row, and a failed migration, an image change or a framework change, which only the disposable qualifiers cover.

## Qualifying a framework release

For a change to `langgraph-checkpoint-postgres`, on a disposable target. `tests/db/upgrade_check.py adapter` does steps 1 and 2:

1. Run the adapter's own `setup()` in a scratch schema, and compare its columns with what migrations own in `agent_runtime`. A difference needs a new migration.
2. Check that the runtime role can't change the schema or qualify an adapter, and that the saver resolves to `agent_runtime`.
3. Replay a saved run through the new release with `scripts/qualify_upgrade.py`.
4. Only then add a migration recording the new fingerprint and version in `agent_runtime.adapter_qualifications`. Get the values from `adapter_identity()`.

## Failure and forward recovery

- **A migration fails:** it rolls back whole, with no history row, and the error is reported. Fix forward with a new or corrected unapplied file. Workers and API stay on `schema_behind`.
- **An applied migration was edited:** refused with `never edit an applied migration`. Restore the file, and put the change in a new one.
- **`incompatible_version` on saved runs:** either run the release that recorded them, or cancel and start linked new runs. Don't edit `execution_contract`.
- **`adapter_unqualified`:** go back to the qualified release, or finish the qualification above.
- **Rolling back the application after a migration:** not supported as a downgrade. Restore the pre-upgrade backup to a new instance, or fix forward.

## Cleanup

The qualifier removes only its own `autobots-disposable-*` project and temporary directory.
