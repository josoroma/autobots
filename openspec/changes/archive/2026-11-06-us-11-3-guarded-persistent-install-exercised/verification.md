# Verification — us-11-3-guarded-persistent-install-exercised

Change: us-11-3-guarded-persistent-install-exercised
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## The install

| | |
|---|---|
| Project | `autobots-install`, unmarked as disposable |
| Ports | Gateway `127.0.0.1:55321`, database `127.0.0.1:55322`, API `127.0.0.1:8001`, web `127.0.0.1:3000` |
| Record and secrets | `~/.local/share/autobots-install`: `install.json`, `stack.env`, `app.env`, `owner.env`, all `0600`, in a `0700` directory. The owner's password is in `owner.env` |
| Data | Five named volumes, `autobots-install_db-data`, `_db-config`, `_storage-data`, `_snippets`, `_edge-functions` |
| Left as | **Containers stopped, data kept, no process running, inference off.** To start: `up`, then the [local app](../../../../docs/engineering/runbooks/local-app.md) processes |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Refuse the wrong target | PASS | `scripts/qualify_persistent_apply.py`, 26 cases on a disposable stack: another project, another install ID, another port, a disposable label on the real path, no identity row, an edited or badly named migration, `reset` and `apply --reset`, each with no change to the history or table counts. A failing migration rolls back whole. On the real install, `reset` and `apply --project supabase_db_finance` exited 1, and its facts and volumes were byte-identical afterward |
| Stand up beside other projects | PASS | Live. `status`: gateway and database listen only on their recorded loopback bindings, and the API and web only on theirs. Operations read ready. 32 lines of other projects' containers, ports and volumes, 20 of them `finance` or `mentor`, were identical before and after the whole exercise |
| Exercise the runbooks on the install | PASS | Live, recorded below |
| Run a real goal under the shared cap | PASS | Live, below. The refusal is on a disposable-side ledger arranged 10 micro-USD below the cap: exit 1, no request, nothing reserved. The real ledger hasn't come near the cap |

## Real goal

Run through the install's real API and `worker.main`, on the key in `.env`, with the switch on for that one process.

| | |
|---|---|
| Goal | `scripts/live_goal.py`'s report, with a required artifact, limit US$0.25, all reserved on the shared ledger first |
| Route | Terra, `openai/gpt-6.1-terra`, the default |
| Outcome | **`succeeded` in 19 seconds**, verification passed, `report.md` published, 592 bytes, sha256 `6f02e46e…` |
| Calls | 6, each with a reported charge |
| Reported cost | **US$0.005973** |
| Key usage | `0.858598285` to `0.864570985`, a rise of US$0.005973 |
| Shared ledger | **US$0.008174 of US$1** across 18 entries, with US-11.2's US$0.002201 |
| Afterward | The worker exited 0, no live worker claims inference, and the key is in no durable row or log |

## Runbooks

| Runbook | Observed | Not exercised |
|---|---|---|
| `local-supabase.md` | Preflight: exit 1 naming the holder on `54321` and `54322`, and pass on the chosen ports. `init`, `up`, `setup`, `apply` of 31 migrations, `status` | Its recovery rows, a pinned-release upgrade |
| `local-app.md` | The processes on their ports, the owner's bootstrap, the key's real save path. A real browser: a wrong password refused, sign-in, the run's page, the artifact's bytes matching their hash, Settings, Operations with no key or address in the text | Studio |
| `operations.md` | `worker_absent` with no worker, then `worker_ready` with one, `claims_inference: false`. A drain: `worker.stopped`, and the web and API down. `compose stop`, `up`. **Owner, run, artifact bytes, checkpoints, events and all five volumes, with their creation times, identical across stop and start and after the backup** | A drain cut short, reconciling a real uncertain call, retention, the GitHub section, real sleep, which is US-11.10. A run paused for an unusable key or a stale catalog |
| `backup-restore.md` | `keygen`. `backup`, refused first as described under Findings, then `backed_up`, with the project healthy again. `restore` into `autobots-disposable-db6e4b68` with `held: true`, while the install kept running. `verify`: 14 of 14. Owner sign-in on the copy, and a wrong password refused. Operations shows the backup's age. The copy was then removed | PostgREST per owner and a checkpoint read through the saver, which the disposable qualifier asserts. Releasing a hold. Another machine |
| `upgrade.md` | One real migration, `20261106000032_terra_reasoning_limit.sql`: read, drained, backed up, restored, **applied first to the restored copy with `--restored-copy`**, then to the install, then the API started. A real browser shows the new limit. Owner, run and artifact unchanged, with one more history row. A repeat applies nothing | `schema_behind`, since this migration only changes a row. A failed migration on the install, an edited one, an image or framework change |

Checks on the final code: `harness`, `fast`, `db` and `operations` all exit 0, and `openspec validate` is clean. `db` now includes `persistent_apply_qualification`. After the live exercise, `init` also tightens the `config` directory, done by hand on this install, and the rest was documentation and formatting.

## Findings

**Found by the real stack, and fixed.**

- **The backup refused the persistent install.** Its fact query named `autobots_disposable.migrations` inside a `CASE`, and Postgres needs a name to exist when it parses, whichever branch runs. So it could only ever have worked on a disposable target. It now decides which history table to read first.
- **`disposable_db.py cleanup` reported PASS and left the restored copy's five volumes,** holding the install's data, because Compose only removes volumes its given file names. It now removes the project's labelled volumes too, and a second run left none.

**Runbooks corrected, as they described something else.** `no_inference_worker` needs a queued job, and `worker.draining` is logged only if a step is still running.

**The first `apply` on the install applied 31 migrations.** The 32nd was written during the exercise, so the upgrade path met a real pending file. It's a true finding from US-11.2, and it adds a sentence to Terra's stored limits.

## Limits

- **One goal on one model, in one sitting.** DeepSeek hasn't run on the install. This shows the path works, and says nothing of task quality.
- **Single short run:** minutes of uptime, one backup, one upgrade, and no long-term use, disk growth or Docker restart of the Mac.
- **The refusal at the cap and the guard's refusals are arranged** on disposable targets. Only the two named refusals ran against the real install.
- **The backup key and the provider key copy are on this Mac,** in the same directory tree, each in its own folder. That doesn't protect from losing this Mac, as the runbook says.
- **Sealed backup remains** in `~/.local/share/autobots-install/backups`, holding this install's data. Nothing removes it.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
