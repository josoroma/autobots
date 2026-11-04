# Runbook: local specification and development harness

## Scope and prerequisites

Run from the Autobots workspace on this Mac with Python 3.12 or later. The hook interpreter is explicitly /opt/homebrew/bin/python3.12 (observed 3.12.16). If python3.12 is absent from PATH, use that absolute path. Plain python3 can resolve to macOS 3.9.6 in another process; unsupported versions fail clearly. Application dependency qualification remains separate. No package installation, API key, model call, Docker or Supabase is needed for these commands. Read the mapped sources in `.claude/autobots.json` and `CODEBASE.md` before changing the backlog.

This runbook covers the implemented `harness` profile. `fast`, `full`, `db` and `operations` remain unimplemented and must return a nonzero unavailable result, not substitute a smaller passing suite. H0/H1 has additional pending requirements.

## Validate the backlog

```sh
python3.12 scripts/specs.py validate
```

Expected: success only when required fields, source locations, Gherkin scenarios, dependency/status rules and generated navigation match the authored stories. This checks structure and traceability locations; it does not certify semantic source agreement or implemented application behavior.

When an authorized story edit makes navigation stale, regenerate only the derived views:

```sh
python3.12 scripts/specs.py render
python3.12 scripts/specs.py validate
```

The renderer must preserve Product Context and all authored story content, IDs, statuses and task checkboxes. A second render should make no change. Invalid source stories must be repaired from evidence, not rewritten merely to satisfy the validator. Missing product behavior stays NEEDS CLARIFICATION; unresolved dependencies/conflicts stay BLOCKED.

## Run the delivered checks

```sh
python3.12 scripts/verify.py --profile harness
```

Expected: project configuration, backlog validation and nonempty behavioral tests pass with unchanged input fingerprints. Inspect `.checks/harness/latest.json` for actual commands, counts and output. Inputs edited during a check invalidate the result. The report excludes secret files and records no live model qualification.

```sh
python3.12 scripts/verify.py --profile db
```

Expected today: exit code 2 with `not_implemented`. It must not start containers or touch a database. This is a checked limitation, not database acceptance.

## Inspect or use the assistant integration

Project configuration is `.claude/settings.json`; the dispatcher is `.claude/hooks/dispatch.py`. The scripts use bounded stdin JSON and invoke no model. The observed Claude Code 2.1.314 is newer than the documented 2.1.295 minimum for blocking hook startup failures; version compatibility is not event-delivery proof.

In a separately qualified compatible assistant session, inspect the loaded project rules, skills, agents and hooks, then test actual event delivery on a disposable fixture. Keep the existing OpenRouter-only constraint; do not add provider credentials or assume product model IDs are supported by the CLI. Until that exercise is recorded, the adapter is **configured, event delivery unverified**. Use the portable runner directly in the meantime.

Invoke `autobots-spec-ingest` for backlog ingestion; the read-only agent proposes content, and its caller writes and validates it. Use the plan/implementation/review/verification/runbook skills for an authorized bounded work item. Do not use ingestion as permission to start product development.

## Failure and recovery

| Symptom | Diagnosis and recovery |
|---|---|
| Stale navigation | Inspect the authored diff; render derived views; validate again |
| Missing source or malformed scenario | Locate the actual source; repair the reference/scenario or preserve the unresolved question; never invent success criteria |
| READY story with unfinished dependency | Keep the dependency and mark the story BLOCKED until its real prerequisite completes |
| Stale harness report | Run the relevant current checks; an old input hash cannot certify edited code |
| `verify.lock` exists | Read the recorded PID and establish whether its verifier is still running; only remove a confirmed stale lock, then rerun. Never delete another active check's lock |
| Completion hook blocks once | Run the portable checker or report the unavailable prerequisite. Repeated Stop processing does not loop forever or claim a missing check passed |
| Secret/destructive command denied | Use the separately authorized, target-guarded credential/maintenance procedure; this coding hook is not a general operations authorization mechanism |

Parser and hook tests use temporary directories and clean up their own fixtures. The upstream clone, application data and unrelated services are not cleanup targets. Do not run reset/prune/down-with-volume-removal to repair this harness.

## Evidence and last exercise

**Last exercised:** 2026-11-04, portable harness and synthetic failure/recovery scope. The exact final input fingerprint and result are in the linked manifest; actual Claude event delivery, Docker and inference were not exercised.

See [HARNESS-ADAPT-001 evidence](../evidence/HARNESS-ADAPT-001/summary.md) for the latest exercised revision, command results, intentional failure cases, independent review and limitations. Raw logs live under ignored `.checks`; reviewed redacted summaries remain versioned. The evidence manifest binds the tested source/configuration fingerprints. No real Supabase or OpenRouter result is implied by these harness commands.
