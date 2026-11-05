## 1. Target-checked wrappers and isolated fixtures

- [x] 1.1 Add `infra/disposable/compose.yaml` and the identity, rendering, label and marker guards in `scripts/disposable_db.py` (Refuse the persistent target)
- [x] 1.2 Test refusals with a fake `docker`, showing none precede a call (Refuse the persistent target)
- [x] 1.3 Add the `db` profile to `scripts/verify.py`, leaving `operations` not implemented (Exercise disposable fixtures)

## 2. Synthetic cases

- [x] 2.1 Add synthetic migrations, seeds and Storage policies under `tests/db/` (Exercise disposable fixtures)
- [x] 2.2 Run replay, upgrade, seed, grant, RLS and Storage negative cases on a real disposable target (Exercise disposable fixtures)
- [x] 2.3 Document the procedure and recovery in the harness runbook (Exercise disposable fixtures)
