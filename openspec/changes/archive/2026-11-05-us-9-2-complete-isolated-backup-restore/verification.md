# Verification — us-9-2-complete-isolated-backup-restore

Change: us-9-2-complete-isolated-backup-restore
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `05baa5a`, working tree with this change. Target: two disposable Compose projects, the source standing in for the persistent stack. Scripted model and an arranged fake credential. No paid call or real credential.

Commands: `python3.12 scripts/qualify_backup.py` (45 cases, exit 0, 90 s), `scripts/qualify_operations.py` (70 cases), `scripts/qualify_identity.py` (242 cases), `scripts/verify.py --profile fast`, `--profile harness`.

## Scenarios

**Restore all required components: observed, source arranged.** The source held real loop output: a finished run with a published artifact, a run paused on an uncertain call, a queued job, and a sealed fake key.
- Backup: versioned manifest naming configuration and all five volumes, images, Compose hashes, 24 migrations and artifact hashes. Directory 0700, files 0600. Provider key kept outside it. No secret, email or database file name found in any backup file. The source came back with the same counts.
- Refused before anything stopped: a live worker. Refused before Docker was touched: the source as target, a non-disposable name, the wrong backup key, a flipped byte in a component, a changed manifest.
- Restore, on its own ports and volumes: owners sign in with their own passwords and a wrong one is refused; PostgREST shows 3 runs to A and none of them to B; runs, events, receipts, invocations and checkpoints match the manifest; the artifact downloads through real Storage with its recorded hash; the credential decrypts by fingerprint with the kept key and not with a different key or none; both checkpoint threads read through the real saver, ending at the manifest's latest.

**Avoid accidental resumed charges: observed.** Under the hold: a claim and a worker pass took nothing and built no model, every job and invocation count stayed the same, the real product worker changed nothing and ran no retention, the API reported `restore_hold` and refused admission with 503, and the runtime role couldn't release the hold. The source's counts, its paused run and its zero holds were unchanged after everything. After a person released it, the restored checkpoint continued to success, with a scripted model and an arranged resume (no usable key for the route).

## Limits

- Harness success is harness evidence only. This doesn't establish H1 or product acceptance.
- Not exercised: a persistent source, a real credential, a real provider, or restoring on another machine. Same-device backups don't protect against losing this Mac.
- `manifest.json` is unencrypted: no secrets, but it does hold identifiers and counts. Backups are physical, so they restore only under the same pinned images, which a later upgrade story must deal with.
- Operations shows backup age from `AUTOBOTS_BACKUP_DIR`. With a real backup there, that display was exercised only by a unit test.
- Reconciling an uncertain call needs a real charge figure. The exercise used an arranged one.
