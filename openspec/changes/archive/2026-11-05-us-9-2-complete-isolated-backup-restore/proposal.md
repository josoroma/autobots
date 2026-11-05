## Why

US-9.2 needs a backup that restores history, artifact bytes and encrypted credentials together, proven on an isolated instance, without a restore replaying paid work.

## What Changes

- `scripts/local_backup.py`: `keygen`, `backup` and `restore`. Backup is cold and encrypted, with a versioned signed manifest. The provider key is kept apart. Restore only creates a new disposable project.
- Installation holds: a restored instance claims nothing, admits nothing and runs no routine or retention pass until an operator releases it. Runtime role can't release.
- Operations shows the hold and the last backup's age.
- Backup and restore runbook, exercised by `scripts/qualify_backup.py` between two disposable stacks.

## Capabilities

### New Capabilities

- `local-backup-restore`: complete backup, isolated restore and the restore hold.

### Modified Capabilities

None.

## Impact

Migration `20261105000024_installation_holds.sql`, `worker_leases`, `goal_loop`, worker maintenance, Operations contract and page, `scripts/local_backup.py`, `scripts/qualify_backup.py`, `docs/engineering/runbooks/backup-restore.md`.
