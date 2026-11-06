# Runbook: backup and restore

A complete local backup, and a restore into a separate instance to prove it works.

**Last exercised:** on the real install on 2026-11-06, [as US-11.3 records](../../../openspec/changes/archive/2026-11-06-us-11-3-guarded-persistent-install-exercised/verification.md), restoring into an isolated `autobots-disposable-*` project. `python3.12 scripts/qualify_backup.py` also runs it between two disposable projects, and asserts more on the restored instance, as listed below. **Restoring over a live instance isn't supported or provided, and neither is moving to another machine.**

Backups on this Mac don't protect you from losing this Mac. Copy the backup and both keys elsewhere, each separately, if that matters.

## Prerequisites and target

- `services/agent/.venv` (the tool needs `cryptography`), Docker, and the pinned images already local. Nothing is pulled.
- `PROJECT` is the Compose project to back up. Check the name.
- `ENV_FILE` is that stack's configuration, including its role passwords: the install's `stack.env`. It's sealed into the backup because Auth signing and role passwords must match the restored data.

## Keys

Three things, stored apart:

| Item | Where | Without it |
|---|---|---|
| Backup directory | `--out` | Nothing to restore |
| Backup key | `--backup-key`, generated once | The backup can't be opened |
| Provider master key copy | `--key-dir`, outside the backup | Saved OpenRouter keys can't be decrypted, and must be entered again |

```sh
services/agent/.venv/bin/python scripts/local_backup.py keygen --out "$BACKUP_KEY"
```

## Take a backup

Stop web, API and workers first, as [the operations runbook](operations.md) says. The tool stops the rest and starts it again afterwards.

```sh
services/agent/.venv/bin/python scripts/local_backup.py backup --project "$PROJECT" --env-file "$ENV_FILE" --out "$BACKUP_DIR/$(date +%Y%m%d-%H%M%S)" --backup-key "$BACKUP_KEY" --key-dir "$KEY_DIR" --master-key "$MASTER_KEY"
```

Expected: exit 0, `{"status": "backed_up", ...}`, the project healthy again. The directory is `0700` with files `0600`.

- `manifest.json` isn't encrypted and holds no secret: versions, image names, Compose hashes, migrations, counts, artifact and checkpoint identifiers, artifact hashes and a hash of the provider key. It does reveal those identifiers and counts. `manifest.hmac` signs it.
- `*.sealed` are AES-GCM in numbered chunks, so a changed, reordered or truncated file fails.
- Set `AUTOBOTS_BACKUP_DIR` for the API, and Operations shows the newest backup's age.

**Refused, with nothing stopped:** a worker or job lease still live, a directory that exists, or keys inside the backup directory. Exit 1.

**If capturing fails partway:** containers still start again, and no `manifest.json` is written. A directory without one is not a backup. Delete it yourself once you've read why.

## Restore into an isolated instance

```sh
services/agent/.venv/bin/python scripts/local_backup.py restore --backup "$BACKUP_DIR/<name>" --backup-key "$BACKUP_KEY" --project "autobots-disposable-$(openssl rand -hex 4)"
```

Expected: exit 0 and JSON naming the new project, its ports and volumes, with `"held": true`.

The whole backup is checked first, with Docker untouched. Refused with exit 1 and nothing created: a changed component or manifest, the wrong backup key, a project that isn't `autobots-disposable-*`, the source itself, a project that already exists, or Compose files or images that differ from the backup. Check out the matching revision for the last two.

## Verify what came back

On your restored instance, this checks every fact in the manifest, and exits 1 on any mismatch:

```sh
services/agent/.venv/bin/python scripts/local_backup.py verify --backup "$BACKUP_DIR/<name>" --backup-key "$BACKUP_KEY" --key-dir "$KEY_DIR" --project "$RESTORED_PROJECT"
```

It covers counts, users, credentials, migrations, checkpoint threads, the provider key's fingerprint, the hold, anonymous reads and every artifact's hash. It can't test your sign-in, so also sign in on the restored instance yourself.

`scripts/qualify_backup.py` additionally asserts each of these on its restored instance:

- Owners sign in with their own passwords, and a wrong one is refused.
- PostgREST shows each owner only their workspace.
- Counts match the manifest, and every published artifact downloads with its recorded hash.
- The credential decrypts with the copy from `--key-dir`, compared by fingerprint so it's never shown, and doesn't with another key or none.
- Checkpoint history reads through the real saver, ending at the manifest's latest checkpoint.

## The hold

A restore starts only the database, writes a row in `app_private.installation_holds`, then starts the rest, so the hold stays even if a later service fails. While it's there, no job is claimed, the worker runs no routine or retention pass, admission answers `503 not_ready`, and Operations says `restore_hold`. So restoring can't replay a paid call or an external write, including with its restored OpenRouter key.

Queued runs and uncertain calls stay exactly as they were. The runtime role can't remove the hold. To release it, on a target you've identified, as the database owner:

```sh
docker compose -p "$RESTORED_PROJECT" exec -T db psql -U supabase_admin -d postgres -c "delete from app_private.installation_holds;"
```

Before releasing, cancel or review what's pending, because workers will take queued jobs afterwards. Uncertain calls still wait for a person: see [the operations runbook](operations.md).

## Failure symptoms

- **`does not open with this backup key`:** wrong key, or a changed file.
- **`workers or job leases are live`:** stop workers, and wait for any lease to expire. Operations shows it.
- **Saved key won't decrypt after restore:** the provider key copy doesn't match. Compare its SHA-256 with `provider_key_sha256` in the manifest.

## Cleanup

The qualifier removes only its own two `autobots-disposable-*` projects and temporary directory. Removing a restored instance you made is your call: `python3.12 scripts/disposable_db.py cleanup --project "$RESTORED_PROJECT"` removes the project's containers and labelled volumes, and nothing else. Nothing removes a backup.
