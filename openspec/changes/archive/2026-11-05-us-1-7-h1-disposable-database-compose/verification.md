# Verification — us-1-7-h1-disposable-database-compose

Change: us-1-7-h1-disposable-database-compose
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `a93f806`, working tree with this change. Real local Docker, with the images already on this machine and nothing pulled. No model call.

## Scenarios

**Refuse the persistent target: observed, with the persistent identity arranged.** No persistent Autobots stack exists yet, so its identity was supplied as arguments, using the LM-04 ports.
- Real commands: `reset --project autobots --db-port 54322`, `cleanup --project autobots-disposable-x --volume autobots_db-data` and `reset` with `DATABASE_URL` naming port 54322 each exit 1, `REFUSED before any change`. The URL's password is not repeated.
- `tests/harness/test_disposable_guard.py`, part of 176 passing harness tests, repeats these with a fake `docker` on `PATH` that records calls: no call was recorded on refusal.
- Ten rendered-configuration faults are each refused: a wildcard bind, a persistent port, an external volume, a foreign volume, an unmarked volume, a bind mount, a floating image, an always-pull policy, missing labels and a renamed project.
- On a real target: a wrong marker refused `reset`, and both fixture notes remained. A project with no containers has no marker, and is refused.

**Exercise disposable fixtures: observed on a real disposable target.** `env -i PATH=… HOME=… scripts/verify.py --profile db`: exit 0, all checks passed, and 34 of 34 cases passed on `autobots-disposable-3087a08c` in about 14 seconds. Raw results: `.checks/db/qualification.json`.

| Area | Observed |
|---|---|
| Replay | Fresh apply of 2; repeated apply 0 with the schema unchanged |
| Failure and history | A failing migration rolled back, 0 tables remain; an edited applied migration refused by checksum |
| Upgrade | 0001 with data, then 0002: `prior body`, `untitled` |
| Seeds | Two runs give the same row hash; a user's edit survives a repeat |
| Database roles | Actual `anon` and `authenticated` roles. Anonymous and authenticated are denied `app_private`, anonymous is denied `app`. A member reads 1 and inserts. The other workspace reads 0, updates 0, and its insert fails on row-level security |
| Storage, real `storage-api` | Member upload and read return the bytes. Anonymous, no token and the other workspace are denied read. Anonymous and the other workspace are denied upload. No public read |
| Isolation | Loopback ports in 55400-55999, generated secrets, labeled volumes. Afterward no project containers or volumes remained, and 32 other Docker containers and volumes were the same before and after |

`PATH=/usr/bin:/bin … qualify` with no Docker reachable exits 2 and starts nothing. `--profile operations` exits 2, `not_implemented`. `full` and `harness` also exit 0.

## Findings

- **A positive control caught a vacuous pass.** Member A at first read 0 notes, so "other workspace reads nothing" proved nothing. This image's `auth.uid()` read the older `request.jwt.claim.sub`. The fixture now sets it, and a member insert was added as a control.
- **A report collision, fixed:** the verifier's report overwrote the qualification report at the same path. Qualification now has its own file.
- **Not the pinned release.** The Postgres `17.6.1.106` and storage-api `v1.35.3` images were already on this machine, used by unrelated projects, and are pinned here by digest. They are not self-hosted v0.8.3, and Auth, the gateway and Studio are absent. US-2.1 owns that, so DH-07's "same pinned Compose family" remains open.
- **Fixture signatures:** Storage tokens are signed by the fixture with a generated secret. They are not issued by real Auth.
- **A marker needs a reachable database, and cleanup does not.** `cleanup` relies on names and labels, so a run that failed to boot can still be removed. Labels could be forged by someone with Docker access, and the guard does not claim otherwise.
- **The persistent-resource comparison compares IDs, names and projects,** not their data. No mutation path to them exists here, and `other_resources` drops status text that changes on its own.
- **Unrelated stacks were not contacted.** Their ports were refused by rule, so nothing connected to them.
- **The Stop hook does not require a `db` report,** only `harness`, `fast` or `full`, by scope.
- **Not exercised:** the recovery row for a killed run, other than `cleanup` of an empty project, which exits 0.
- **Runbook:** the added section's commands were run as written, except that recovery.
- This is not H0, H1 or product acceptance.
