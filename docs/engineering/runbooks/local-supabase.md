# Runbook: pinned local Supabase

## Scope and prerequisites

The pinned release is `self-hosted/v0.8.3`, commit `bc27d2661edd09a5d0b8d76ce33da6d4071a756e`, vendored unmodified in `infra/supabase/upstream/` with hashes in `UPSTREAM.json`. `infra/supabase/compose.overlay.yaml` holds local decisions. This covers preflight, disposable qualification and [the persistent install](#the-persistent-install).

Needs Docker with the eight images in the overlay already local, and the prepared `services/agent/.venv` for the direct connection check. Nothing is pulled by a check.

## Preflight

```sh
python3.12 scripts/supabase_stack.py preflight
python3.12 scripts/supabase_stack.py preflight --gateway-port 55400 --db-port 55401
```

Expected: exit 0 when free. When held, exit 1, one `CONFLICT:` line naming the holder, and nothing is stopped. The proposed ports are `54321` and `54322`. On this machine they are currently held by another project's stack on wildcard addresses, so the first command exits 1. Stop that stack yourself or choose other ports; the script never does.

## Qualify

```sh
python3.12 scripts/supabase_stack.py qualify
jq -r '.status, .project, .images[], (.cases[] | "\(.status) \(.id): \(.observed)")' .checks/supabase/qualification.json
```

Expected: exit 0 in about a minute. It creates a new `autobots-disposable-<id>` project with generated secrets on free loopback ports in 55400-55999, and removes only that project. `--profile db` runs this too.

It checks the merged Compose result, then actual listeners: both published ports on `127.0.0.1` only, the direct port reaching the `db` container's cluster on server port 5432, Studio returning 401 without the operator password and answering with it through the gateway, signup disabled, and Studio's `OPENAI_API_KEY` empty even when the host sets one.

## Failure and recovery

| Symptom | Recovery |
|---|---|
| Exit 2 naming an image | Pull that exact tag deliberately. The check never pulls |
| A run was killed and left a project | `python3.12 scripts/disposable_db.py cleanup --project autobots-disposable-<id>`, which removes that project's containers and labelled volumes |
| `every service is healthy` fails | Its stderr and the case's `observed` name the states. Nothing persistent is involved, and the project is removed anyway |
| Upgrading the release | Vendor new files, regenerate `UPSTREAM.json`, re-resolve digests, and requalify. Never edit vendored files in place |

## Migrations and seeds

Application schema lives only in `supabase/migrations/`. Files are named `<14 digit timestamp>_<description>.sql` and never edited once applied. `supabase/seeds/reference.sql` holds reference rows, and repeats without overwriting a user's edit. `supabase/bootstrap/roles.sql` creates `autobots_migrator`, the only role that runs DDL, and `autobots_runtime`, which cannot.

```sh
python3.12 scripts/app_db.py qualify
python3.12 scripts/app_db.py types
jq -r '.status, (.cases[] | "\(.status) \(.id)")' .checks/app_db/qualification.json
```

Expected: `qualify` exits 0, after creating a new disposable database and Storage on the pinned images, proving replay, upgrade from the prior version, seeds, the bootstrap history, constraints, access and migration authority, and removing them. It fails if `packages/db-types/src/generated.ts`, the row types of the columns `authenticated` can select, or `supabase/schema.snapshot.sql`, the schema for reading, has drifted. After a migration or bootstrap change, `types` runs the same cycle and rewrites both files. Exit 2 means Docker or the pinned image is missing. `--profile db` runs `qualify`.

## The persistent install

`scripts/persistent_install.py` is the only path that changes the persistent database. There's one install, recorded outside this repository in `~/.local/share/autobots-install`: `install.json` holds its identity and ports, and `stack.env`, `app.env` and `owner.env` its secrets, all mode `0600`. Data is in the Compose project's named volumes. No command here removes a container or a volume, and `reset` is always refused.

```sh
PYTHON=services/agent/.venv/bin/python
$PYTHON scripts/persistent_install.py init --project autobots-install
$PYTHON scripts/persistent_install.py up --project autobots-install
$PYTHON scripts/persistent_install.py setup --project autobots-install
$PYTHON scripts/persistent_install.py apply --project autobots-install
$PYTHON scripts/persistent_install.py status --project autobots-install
```

`init` refuses a held port, a disposable name or an existing record, and touches no database. `up` refuses a Compose result that isn't loopback-only with pinned images. `setup` runs the role bootstrap and writes the identity row in `autobots_install.identity`, once, on a database with no application tables. `apply` applies pending migrations in order, each with its history row in one transaction, as the migration role, then the seed, then the pending files in `supabase/bootstrap/` as the database superuser, each with its own `bootstrap/<file>` history row in one transaction: `storage.sql` first, then the files named `<14 digit timestamp>_<description>.sql` in name order. Those hold what the migration role can't own, such as Storage's policies. The framework's checkpoint tables are created by those migrations, and workers never call its `setup()`.

**Before `make migrate` on an existing install,** run each query in the header of `supabase/migrations/20261115000061_integrity_validated.sql` on it. Migration 61 validates the draft shape check and the version keys that migrations 59 and 60 add, and stops on any row those queries return. They read `app_private`, so run them as the database superuser, `supabase_admin`, over the database container's own socket, where no password is typed or shown: `docker compose -p autobots-install exec -T db psql -U supabase_admin -d postgres -X -c "<query>"`. Each query only reads. If one returns rows, back up first, then correct those rows with a reviewed change sent the same way inside `begin;` and `commit;`, and run `make migrate` again.

**Before any change,** `apply` refuses a project that isn't the recorded one, a target with no running database, a disposable label, a database published on another port, an identity row that doesn't match, an edited applied migration or bootstrap file, an applied one this checkout lacks, or a badly named file. `status` lists the actual listeners. `python3.12 scripts/qualify_persistent_apply.py`, in `--profile db`, tests each refusal on a disposable target. A real install's stop and start use `docker compose -p autobots-install stop` and `up`, as in [the operations runbook](operations.md).

**Not exercised on the install:** this page's recovery rows, which are about disposable projects, and upgrading the pinned release.

## Credentials and the master key

`autobots.application.credentials` resolves `OPENROUTER_API_KEY` in MP-03's order, and stores app credentials encrypted in `app_private.provider_credentials`. The master key lives at `AUTOBOTS_PROVIDER_MASTER_KEY_FILE`, by default under `~/Library/Application Support/Autobots/secrets/`, outside the repository and any tool workspace. It is created once, on the first save, with a `0700` parent and a `0600` file.

**If it is lost, stored credentials cannot be recovered.** Reads and writes report unavailable storage, and no replacement is generated while encrypted rows exist. Restore the key from its own backup, which is separate from any database backup. Re-entering credentials after a real loss needs an explicit procedure that does not exist yet.

## Removed from the release

Realtime, Edge Functions and the Supavisor pooler are in the `removed` profile, per LM-03 and LM-04. Studio's and Storage's writable bind mounts became named volumes, so data never lands in the vendored directory.
