# Verification — us-9-1-local-startup-shutdown-health

Change: us-9-1-local-startup-shutdown-health
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `c9d4c6f`, working tree with this change. Target: a new disposable Compose project with a scripted model. No persistent stack, real credential or model call was used.

Commands: `python3.12 scripts/qualify_operations.py` (70 cases, exit 0, 80 s), `python3.12 scripts/qualify_identity.py` (242 cases including 3 Operations browser tests, exit 0), `scripts/app_db.py types`, `scripts/generate_contracts.py check`, `scripts/verify.py --profile fast`, `--profile harness`.

| Scenario | Result | Observed |
|---|---|---|
| Start and stop without data loss | PASS, arranged | The persistent stack isn't configured, so a disposable project stands in. Order followed: infrastructure, migrations, processes. Admission passed the gate only when ready, and answered 503 with no new job when Storage or the database was down or disk arranged low. SIGTERM inside a model call: heartbeat `draining`, the run finished `succeeded`, no lease left. A drain past its bound exited 0 and left the job recoverable, and the run paused on an uncertain call instead of repeating it. After `compose stop` and `up`: same volumes, same counts of runs, events, receipts, checkpoints and keys, a row written just before shutdown, identical Storage bytes, and the running API reconnected by itself. After owner reconciliation and an arranged resume (no key exists, so the command the route calls), it succeeded with no repeated effect. |
| Expose safe operational evidence | PASS | Each of Storage down, database down (`scope: installation`, API still answering), disk low (arranged), expired lease (natural) and absent worker visible through the API. The body has no address, secret or identifier. A secret-shaped value and connection string planted through the real logger came out `[redacted]`, and no log file held the runtime password, service key, JWT secret, internal token or a planted trace key. Inherited LangSmith settings read `disabled`, and langsmith itself reads tracing as off. Merged Compose names no collector. Browser: owner sees conditions, member refused. |
| Apply declared retention without erasing recovery evidence | PASS | On a real finished run: no window removes nothing; a window removes checkpoints, blobs and files and expires artifact bytes, keeping run, events and receipts. Unknown and started effects, an active tree, an active continuation, an open obligation, a young run and an active run are refused, each keeping its files. A Storage failure leaves bytes pending, removed on the next pass. An old key expires, a key for an active run stays, and effect receipts stay. Another workspace's run is untouched and refused across workspaces. Runtime and signed-in roles can't delete directly. The worker's own pass ran. |

## Limits

- Harness success is harness evidence only. This doesn't establish H1 or product acceptance.
- Not exercised: the persistent stack and its migration apply (no guarded apply exists), real Mac sleep, resume through its route, resource use under load, Docker's VM disk.
- The product worker claims no job. Nothing runs a goal outside fixtures until inference is qualified and wired (US-3.4).
- PRD 12.2's full metric list (queue wait, inference wait, tokens and so on, as log records) isn't implemented: logs cover worker lifecycle, degradation and retention, and durable tables hold the rest.
- What retention covers (events and goal text stay) and that no minimum window exists beyond one day are this story's reading, for the owner to confirm. A purged run's page doesn't explain the missing artifacts.
