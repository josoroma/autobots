# Autobots: set up, start and stop

How to run Autobots on this Mac. The app processes run natively and Supabase runs in Docker. All of it listens on `127.0.0.1` only.

| Process | Runs as | Address |
|---|---|---|
| Web app | Native Next.js | `http://127.0.0.1:3000` |
| API | Native Python | `http://127.0.0.1:8001` |
| Worker | Native Python | No port |
| Supabase gateway (Auth, Storage, Studio) | Docker, project `autobots-install` | `http://127.0.0.1:55321` |
| Postgres | Docker, project `autobots-install` | `127.0.0.1:55322` |

The [`Makefile`](Makefile) wraps the project's scripts. Run every command from the repository root.

## Quick reference

| Command | What it does |
|---|---|
| `make first-time` | Sets everything up, once |
| `make start` | Starts the containers, API, web app and worker, with inference off |
| `make stop` | Stops all of it and keeps your data |
| `make status` | Shows each process and what's listening |
| `make logs` | Follows the API, web and worker logs |

`make` on its own lists the main commands.

## First-time setup

If an install already exists on this Mac, `make first-time` refuses and changes nothing. Skip to [Start](#start).

### 1. Install the prerequisites

Nothing in this repository installs these. The versions must match exactly, except Docker. Only Apple Silicon Macs are qualified.

| Tool | Version | Notes |
|---|---|---|
| Docker, such as Docker Desktop | A current version with Compose | Must be running. Compose v5.6.1 is what's been run here |
| `python3.12` | 3.12.16 | On your `PATH`, for example from Homebrew |
| `uv` | 0.13.6 | On your `PATH` |
| `node` | 22.23.2 | Through nvm, in `~/.nvm/versions/node/v22.23.2` |

Check what's installed. Before step 2, `through_corepack` and `through_package_script` are null in the output, which is expected.

```bash
python3.12 scripts/toolchain.py versions
```

You don't need to install `pnpm` or run `corepack enable`. The scripts handle pnpm inside the repository.

### 2. Run the setup

```bash
make first-time
```

This downloads packages and Docker images, so it needs network access. It makes no model calls and costs nothing. It runs these steps in order:

| Step | What it does | If it fails, continue with |
|---|---|---|
| Toolchain | Installs Python and Node packages from the lockfiles, inside the repository | `make toolchain` |
| Images | Pulls the eight pinned Supabase images. No other command pulls them | `make images` |
| `init` | Records the install and generates its secrets in `~/.local/share/autobots-install` | See the note below |
| `up` | Starts the containers | `make start-stack` |
| `setup` | Creates the database roles and the install's identity row | `services/agent/.venv/bin/python scripts/persistent_install.py setup --project autobots-install` |
| `apply` | Applies the migrations and reference seed | `make migrate` |
| Build | Builds the web app | `make build` |
| Owner | Creates your owner account and a workspace named `Personal` | `make owner` |

**If it stops partway,** rerunning `make first-time` is refused once `init` has run. Fix the cause, then run the command for the failed step and each step after it. `init` itself refuses a port that's already in use and writes nothing in that case, so free the port and run `make first-time` again.

`setup` and `owner` are meant to run once. If one fails partway, for example after the owner's user is created but before its workspace, a retry can be refused, and there's no documented recovery for that yet. Read the error before you retry, and don't reset anything to get past it.

To name the workspace yourself, use `make first-time WORKSPACE="My workspace"`.

### 3. Start and sign in

```bash
make start
```

Open `http://127.0.0.1:3000`. Use `127.0.0.1`, because `localhost` can be refused as `forbidden_origin`.

Public signup is disabled, so sign in as the generated owner. This command prints the email and password in your terminal:

```bash
grep OWNER_ ~/.local/share/autobots-install/owner.env
```

### 4. Add your OpenRouter key

Go to **Settings → Models → OpenRouter → Save & validate**. The key is checked, encrypted and stored. Saving it doesn't start a run or spend money.

The app does **not** read `.env` in the repository root. Only the paid qualification scripts use that file. The app reads its environment and any `.env` files in `~/.local/share/autobots-install/config`, but an environment key only applies to a workspace that has been granted it, so use Settings.

Without a key, sign-in, settings and drafts still work, and **Run** answers `credentials_required`.

### 5. Set up backups

Saving a key creates the master key that encrypts stored credentials, in `~/.local/share/autobots-install/config/secrets/`. **If it's lost, stored credentials can't be recovered.** Set up backups with [the backup runbook](docs/engineering/runbooks/backup-restore.md). Before a backup, run `make stop-app`, not `make stop`, because the backup needs the containers running. The backup also refuses to run until that master key exists, so save a key first.

## Start

```bash
make start
```

This starts the containers, API, web app and worker, and reports an error if the API or web app doesn't answer. Running it again is safe, since anything already running is left alone. Docker has to be running first, including after a reboot.

It doesn't apply migrations or rebuild the web app. See [Updating the code](#updating-the-code). It also starts the worker once the API and web app answer, without waiting for the Operations page to say ready, so check that page if something looks wrong.

The `make` commands only stop what they started. Something else may hold the API or web port, or run a worker: a process you started by hand from a runbook, or one whose pid file was lost. In that case `make stop` reports it by pid and leaves it running, since a worker may be in a paid call. `make start` refuses to start beside it, so you won't end up with two workers. Stop it yourself with the `kill -TERM <pid>` the message gives, then run `make start` again. A worker keeps billing until it stops if its inference is on.

## Stop

```bash
make stop
```

This stops the web app, API and worker, then the containers. Your data stays in Docker's named volumes, and the next `make start` picks it up.

The worker gets up to 30 seconds to finish a running step. If a process is still running after 45 seconds, `make stop` reports it, still signals the other processes, leaves the containers up and doesn't force anything. A step still running can be in the middle of a paid call, so read [the drain procedure](docs/engineering/runbooks/operations.md#drain-and-stop) before you take any further action.

To stop only the web app, API and worker and leave the containers running, use `make stop-app`.

## Running goals costs money

**Inference is off by default, so goals you run stay queued.** Operations shows `no_inference_worker`, and that's expected. No model is called and nothing is billed.

To process them, restart the worker with inference on:

```bash
make stop-worker && make start-worker INFERENCE=enabled
```

**This spends real money. Every queued run, in every workspace with a key, sends billed requests to OpenRouter.** A goal can also keep calling while it drains. To turn inference off, restart the worker without the setting:

```bash
make stop-worker && make start-worker
```

A plain `make start` never turns inference on, and it leaves a running worker as it is. If that worker has inference on, it stays on. [The operations runbook](docs/engineering/runbooks/operations.md#turning-on-inference) explains what each pause reason means.

## Updating the code

**Before you move to new code,** see whether it changes the database, the Supabase stack or the Python packages. Replace `<new>` with the branch or commit you're moving to:

```bash
git diff --stat HEAD <new> -- supabase infra/supabase services/agent/uv.lock
```

If you've already pulled or merged, use `git diff --stat ORIG_HEAD HEAD -- supabase infra/supabase services/agent/uv.lock` instead. `ORIG_HEAD` only covers the last pull or merge, so after several, compare from the last revision you actually ran. The install doesn't record that revision for you.

### If that lists nothing

```sh
make stop-app
git merge <new>
make toolchain
make build
make start
```

Use `git pull` in place of `git merge` if this checkout has a remote.

### If that lists anything

Follow [the upgrade runbook](docs/engineering/runbooks/upgrade.md). It doesn't name these commands, so use them in this order:

1. Run `make stop-app`, not `make stop`. The backup needs the containers running, and it stops them itself.
2. Still on the old code, back up and restore to a copy, as the runbook says. A backup only restores with the Compose files and images it was taken with, so if you've already moved, go back to the old revision first. If no key was ever saved, the backup refuses for lack of a master key, and neither this guide nor the runbook has a way around that yet.
3. Move to the new code, then run `make toolchain` and `make build`. If `infra/supabase` changed, also run `make images`.
4. Try the migrations on the restored copy, as the runbook says.
5. If an image changed, know that the next `make start-stack` or `make start` recreates its container on the new image, over your live data. An image change hasn't been exercised on the real install, so treat it with care.
6. Run `make start-stack`, then `make migrate`, so the migrations run on the new images.
7. Run `make start`.

`make start` never applies migrations. If you start without them, the API reports `schema_behind` and refuses new work until they're applied. The worker doesn't make that check, so it keeps evaluating routines and applying retention against the old schema. Run `make stop-worker`, and apply the migrations before your next `make start`, which starts it again.

## Where everything lives

| What | Where |
|---|---|
| Install record and secrets | `~/.local/share/autobots-install`: `install.json`, `stack.env`, `app.env`, `owner.env` |
| Logs | `~/.local/share/autobots-install/logs`: `api.log`, `web.log`, `worker.log` |
| Backups | `~/.local/share/autobots-install/backups` |
| Database and files | Docker named volumes, `autobots-install_*` |
| Packages and caches | Inside the repository, ignored by Git |

**To keep your data, don't run** `docker compose down -v`, `docker volume rm` or `docker system prune`. Those can delete the volumes, and only a backup can bring them back. No `make` command removes a container or a volume, and `persistent_install.py reset` is always refused.

To use different ports, choose them when the install is created. They're recorded in `install.json`, and every later `make` command reads them from there:

```bash
make first-time GATEWAY_PORT=55421 DB_PORT=55422 API_PORT=8101 WEB_PORT=3100
```

## Troubleshooting

| Symptom | What to do |
|---|---|
| `make start` says a process isn't answering, or exited | Read that process's log, named in the message |
| `Python API: unavailable` | Run `make status`. If the API is running, read `api.log` |
| `forbidden_host` or `forbidden_origin` | Use `http://127.0.0.1:3000`, not `localhost` |
| `The web app is not built` | `make build` |
| Exit 2, `<tool> <version> is required and was not found` | That exact version is missing or moved, for example after `brew upgrade`. Install it, and don't run `uv self update` |
| Exit 2, `not prepared` | `make toolchain` |
| `the stack did not start`, naming a missing image, or an image `is not on this machine` | On a first install, `make images`. After a pull, **stop**: the pinned image changed, and pulling it lets the next start recreate the database on it. [Follow the upgrade runbook](docs/engineering/runbooks/upgrade.md) first |
| `refused. pid <n> looks like a copy of the api` (or web, or worker) | A copy this install doesn't track is still running. Check it with `ps -o pid,lstart,command -p <n>`, stop it with `kill -TERM <n>`, then `make start` |
| `not answering at`, and `Something else may hold the port` | Another program took the port during start, or the process failed to start. Read the log it names. The message `answering` only appears when our own process holds the port |
| `init` refuses a held port | Stop whatever holds it, or [choose other ports](#where-everything-lives) |
| `503 not_ready` | Read the conditions on the Operations page. [The health table](docs/engineering/runbooks/operations.md#reading-health) says what each one means. A disk with under 2 GiB free refuses new work by itself |
| `schema_behind` | See [Updating the code](#updating-the-code) |
| A goal stays queued | Inference is off. See [Running goals costs money](#running-goals-costs-money) |
| A run is paused | Read its reason in [the pause table](docs/engineering/runbooks/operations.md#turning-on-inference). Some reasons wait for a person on purpose |

## Checks

Run the repository checks, with no services or model calls:

```bash
make check
```

The other profiles are in [`AGENTS.md`](AGENTS.md#commands). A pass from any of them doesn't establish H1 or product acceptance.

## How much of this has been exercised

- **The underlying steps** ran on the real install on 2026-11-06, as [US-11.3 records](openspec/changes/archive/2026-11-06-us-11-3-guarded-persistent-install-exercised/verification.md): `init`, `up`, `setup`, `apply`, the owner's bootstrap, the processes, a stop and a start.
- **The Makefile's process handling** ran on fake values with no database, using `start-api`, `wait-ready`, `start-worker` and `stop-app`: starting, already running, stale pid files, a port held by something else, ports read from `install.json`, stopping, and the inference setting reaching the worker. `stop-stack`'s refusal of another project ran too. `make build` and `make check` ran for real.
- **Not yet run through the Makefile:** `first-time`, `toolchain`, `images`, `install`, `owner`, `migrate`, `start`, `stop`, `start-stack`, a `stop-stack` that stops something, `status` and `logs`, and anything against the real install. `make first-time` hasn't been run on a clean Mac.

## More detail

- [Local app](docs/engineering/runbooks/local-app.md)
- [Local Supabase and the persistent install](docs/engineering/runbooks/local-supabase.md)
- [Operations](docs/engineering/runbooks/operations.md)
- [Toolchains](docs/engineering/runbooks/toolchains.md)
- [Backup and restore](docs/engineering/runbooks/backup-restore.md)
- [Upgrades](docs/engineering/runbooks/upgrade.md)
- [Mac sleep](docs/engineering/runbooks/mac-sleep.md)
