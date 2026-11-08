# Tasks

## 1. Probe times (Values beside checks)

- [x] 1.1 Record each readiness probe's database answer time in a 20-probe window in the API process, with no tracing, and report the p95

## 2. Read model (Values beside checks; Numbers only, and nothing more)

- [x] 2.1 Add `OperationValues`, holding exactly D5's list, to `LocalStatus`, with the migration-count function, and regenerate OpenAPI and the TypeScript client

## 3. Page (Verdict; Values beside checks; Existing sections stay)

- [x] 3.1 Render the verdict line and each check's value on Operations, keeping every existing section

## 4. Coverage

- [x] 4.1 Cover the values offline in `test_operation_values.py`, the grants in `app_db.py`, and the four scenarios on a disposable stack in `operations-values.spec.ts` with axe
