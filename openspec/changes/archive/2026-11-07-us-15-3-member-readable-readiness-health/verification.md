# Verification — us-15-3-member-readable-readiness-health

Change: us-15-3-member-readable-readiness-health
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

- **Completeness:** 5 of 5 tasks complete. 1 requirement added to `operations-status`.
- **"All ready":** observed in `python3.12 scripts/verify.py --profile db` (exit 0), browser test "all local services ready", run by `scripts/qualify_identity.py` as a separate pass. The setup was:
  - a reader who is only a member of workspace A, not its owner;
  - a worker heartbeat dated ahead so it stays fresh, removed afterwards;
  - a key the fake upstream accepts, saved by the owner and disconnected afterwards.
  
  The test asserts:
  - the shell line reads "All local services ready";
  - Home's chips read "Python API ready", "Worker ready", "Database ready" and "OpenRouter authenticated";
  - axe reports no violations.
  
  This is arranged disposable evidence. The fixture worker doesn't write heartbeats, so the arranged row stands in for one.
- **"Name the service that isn't ready":** observed in the same `db` run, browser test "names the service that isn't ready", where no worker heartbeat exists:
  - the line has `data-health="worker"` and reads "Worker not ready";
  - the worker chip reads "Worker not ready", and the API and database chips read ready;
  - axe reports no violations;
  - Runs still opens with the line unchanged.
- **"Nothing private in the member read":** observed in the same browser test. The `/api/v1/readiness` body has only `schema_version`, `ready` and `services`, and each service has only `name`, `state` and `code`, with no digits or paths in its code. `services/agent/tests/test_readiness.py` (4 tests, passed in `full` and `fast`) also covers:
  - all ready;
  - a worker without a heartbeat (`worker_absent`);
  - a missing key (`auth_missing`);
  - a database that's down (worker and OpenRouter `unknown`);
  - the exact key set;
  - a 403 for a non-member and for a workspace header the user doesn't belong to.
  
  The read uses `ProviderSettings.auth_status`, which reads stored state only, with no catalog fetch or model call (`application/provider_settings.py`).
- **Found during verification:** the first `db` run failed both browser tests, because each chip's name and state had no space between them ("Workernot ready"). Task 2.3 fixed it. Then `db` (exit 0) and `fast` (exit 0) passed on the final inputs.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
- **Limit:** for a user with several workspaces and no workspace header, readiness uses the first workspace by ID, the same one the account footer treats as current.
