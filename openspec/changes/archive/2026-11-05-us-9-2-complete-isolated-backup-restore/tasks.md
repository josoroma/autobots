## 1. Backup and restore (scenario: Restore all required components)

- [x] 1.1 Sealed, chunked components and a signed versioned manifest
- [x] 1.2 Cold capture of named volumes, refused while workers or leases are live, and source restarted
- [x] 1.3 Restore to a new isolated project, with damage and wrong targets refused before Docker is touched

## 2. Hold (scenario: Avoid accidental resumed charges)

- [x] 2.1 Installation hold stops claims, worker passes, admission, routines and retention
- [x] 2.2 Operations shows the hold and backup age

## 3. Exercise (all scenarios)

- [x] 3.1 `scripts/qualify_backup.py` between two disposable stacks, with real local assertions
- [x] 3.2 Backup and restore runbook
