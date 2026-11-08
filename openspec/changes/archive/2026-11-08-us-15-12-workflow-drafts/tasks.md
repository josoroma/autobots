# Tasks

## 1. Data (One saved draft)

- [x] 1.1 Add one draft per workflow by migration, with RLS that lets only the owner write it, and negative tests in `app_db`

## 2. API (Publish from the draft; Discard; Runs bind only published versions)

- [x] 2.1 Save, publish under the expected version and discard the draft in the application layer, and refuse a draft wherever a run or routine binds a version
- [x] 2.2 Expose them in Pydantic and FastAPI, regenerate the contract and client, and forward them through the BFF's existing routes

## 3. Editor and coverage

- [x] 3.1 Save, publish and discard the draft from the workflow editor
- [x] 3.2 Cover the scenarios on a disposable stack (`app_db` RLS cases) and in `workflows.spec.ts`
