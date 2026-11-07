# DOC-SETUP-001 — First-time setup, start and stop guide

Status: SHORT RECORD, no evidence manifest

A short record, as `AGENTS.md` allows for small changes. Neither a story's acceptance nor the user asks for a manifest, so `scripts/evidence.py` doesn't apply. No story, requirement or application behavior changed.

## Plan

User request: add `README-SETUP-RUN.md` covering first-time setup and starting or stopping later, with a Makefile if useful. A thin Makefile over the guarded scripts, with no new database path. `make start` applies no migrations and leaves inference off. Do not run anything against the persistent install, install dependencies or call a model.

## Implementation

Added `README-SETUP-RUN.md`, `Makefile` and this record. The Makefile wraps `scripts/toolchain.py` and `scripts/persistent_install.py`, and runs the API, web and worker with pid files and logs under the install directory. Its variables ignore the environment, so a shell export can't choose another stack or enable inference. `stop-stack`, the one command outside the guarded script, compares its project with `install.json`. A process is identified by pid and start time.

## Review

Independent read-only review by a separate `autobots-reviewer` agent, three rounds.

- **Round 1, 13 findings.** Fixed: exported variables choosing the target or enabling inference, upgrades skipping the runbook, the backup order, another server satisfying readiness, the stale-pid match, `make stop` halting at the first timeout, the missing `.NOTPARALLEL`, and small factual errors.
- **Round 2, four new.** Two came from the round 1 fixes: custom ports losing track of processes, and a live process with no listener counting as stopped. Also a pre-pull check that couldn't run, as this checkout has no remote, and an overstated help sentence. All fixed.
- **Round 3, four new.** Fixed: the start time depending on the shell's timezone and locale, and the order of an image change. Documented: the backup refusing without a master key, and `ORIG_HEAD` covering only the last merge.
- **Left as documented limits:** the worker starts without Operations readiness, because `local-status` needs a signed-in user. `setup` and `owner` can't be retried safely after a partial failure. Hand-started processes aren't tracked.

The round 3 fixes were not reviewed again. Their process-identity change was rerun on fixtures, as below.

## Verification

Observed on 2026-11-06, with a scratch install directory, fake values, no database and spare ports:

- Start, already running, stop and the status lines, with ports read from `install.json`.
- Exported `API_PORT`, `PROJECT`, `INFERENCE` and `INSTALL_DIR` ignored. `INFERENCE=enabled` on the command line reaching the worker, with `claims_inference: true` in its log and nothing to claim.
- `stop-stack` refusing another project, a held port failing `wait-ready`, a pid with another start time left unsignalled, a live process with no listener still stopped, and status unchanged under another timezone and locale.

`make build` and the harness checks ran for real, and every README link and anchor resolves.

**Not run:** `first-time`, `toolchain`, `images`, `install`, `owner`, `migrate`, `start`, `stop`, a `stop-stack` that stops something, `logs`, the upgrade list, and anything against the real install. A project hook refused a read of the install's directory, and no check went around it. Class: fixture and static, with no model transport. This establishes neither H1 nor product acceptance.

## Runbook

The guide points to the existing runbooks and changes no operating procedure. The steps it wraps were last exercised on the real install by US-11.3. Only the harness verification from [the development harness runbook](../runbooks/development-harness.md) was exercised here.
