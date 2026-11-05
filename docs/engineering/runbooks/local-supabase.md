# Runbook: pinned local Supabase

## Scope and prerequisites

The pinned release is `self-hosted/v0.8.3`, commit `bc27d2661edd09a5d0b8d76ce33da6d4071a756e`, vendored unmodified in `infra/supabase/upstream/` with hashes in `UPSTREAM.json`. `infra/supabase/compose.overlay.yaml` holds local decisions. This covers preflight and disposable qualification. **Starting a persistent stack is not implemented here**, and nothing below creates or changes one.

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
| A run was killed and left a project | `python3.12 scripts/disposable_db.py cleanup --project autobots-disposable-<id>` |
| `every service is healthy` fails | Its stderr and the case's `observed` name the states. Nothing persistent is involved, and the project is removed anyway |
| Upgrading the release | Vendor new files, regenerate `UPSTREAM.json`, re-resolve digests, and requalify. Never edit vendored files in place |

## Migrations and seeds

Application schema lives only in `supabase/migrations/`. Files are named `<14 digit timestamp>_<description>.sql` and never edited once applied. `supabase/seeds/reference.sql` holds reference rows, and repeats without overwriting a user's edit. `supabase/bootstrap/roles.sql` creates `autobots_migrator`, the only role that runs DDL, and `autobots_runtime`, which cannot.

```sh
python3.12 scripts/app_db.py qualify
python3.12 scripts/app_db.py types
jq -r '.status, (.cases[] | "\(.status) \(.id)")' .checks/app_db/qualification.json
```

Expected: `qualify` exits 0, after creating a new disposable database on the pinned image, proving replay, upgrade from the prior version, seeds, constraints, access and migration authority, and removing it. It fails if `packages/db-types/src/generated.ts` has drifted. After a migration change, `types` runs the same cycle and rewrites that file. Exit 2 means Docker or the pinned image is missing. `--profile db` runs `qualify`.

**No persistent apply exists.** Applying to a persistent stack needs a target-identity and baseline check that belongs with whichever story first starts one. The framework's checkpoint tables are set up in `agent_runtime` by the migration identity during qualification only; a persistent path must do the same, and workers must never call its `setup()`.

## Removed from the release

Realtime, Edge Functions and the Supavisor pooler are in the `removed` profile, per LM-03 and LM-04. Studio's and Storage's writable bind mounts became named volumes, so data never lands in the vendored directory.
