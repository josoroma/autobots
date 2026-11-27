# Tasks: US-23.1, a local model route through the shared gateway

## 1. Profiles and SQL

- [x] 1.1 Add `local_bonsai_2_5_27b` and `local_inkling_2_mini` to `domain/models.py`, with `LocalServing` holding the repository, revision, file, SHA-256, template hash and thinking switch. Both are approved and not offered, with not-offered messages. Checked by pytest under `services/agent/tests`.
- [x] 1.2 Add migration `20261127000068_local_model_profiles.sql` with its header lines. It extends the three profile checks and inserts both `model_profiles` rows. Checked by the harness migration-header test, and by the db profile's disposable fixtures.

## 2. The loopback client and the factory

- [x] 2.1 Add `adapters/models/local_server.py`. `served_model` checks the served model ID, and `LoopbackClient` provides `chat.send`, `chat.send_async` and both streamed forms. It sends no key and makes no retries, removes OpenRouter-only parameters, adds the thinking switch, sends one named tool as `required` with only that tool, removes `reasoning_content`, and reports cost 0. Checked by pytest with a fake server on loopback.
- [x] 2.2 Give `factory.prepare_attempt` and `factory.chat_model` their local branch: no catalog, the local parameter set, and the same `ChatOpenRouter` on the loopback client. Checked by pytest.

## 3. Worker inference and the failure class

- [x] 3.1 Add `FailureClass.LOCAL_MODEL_SERVER_UNAVAILABLE` and `StopCode.LOCAL_MODEL_SERVER_UNAVAILABLE`, disposed SUSPEND, to `test_stop_codes`' table. Checked by pytest.
- [x] 3.2 In `worker_inference`, for a local profile: no catalog and no credential, a worst case of 0, and an identity check before each attempt. A mismatch raises `model_unavailable`, and a stopped server raises `local_model_server_unavailable`. Checked by pytest: a run's call answered by a fake server, with an invocation ticket and a receipt, settled at US$0 and counted in `model_calls`, while a fake OpenRouter transport fails if touched. A stopped server and a wrong model each send nothing.
- [x] 3.3 Test that a run on a local profile stops on its model calls, tool dispatches and active time with the codes an OpenRouter run stops with, sending nothing. Test that a Terra run is unchanged and never touches the loopback. Checked by pytest.

## 4. Offering and contracts

- [x] 4.1 Leave local profiles that aren't offered out of the model-policy listing. Test that a new run, the workspace default, a role override and an Expert's role binding naming either are refused `model_not_offered`. Checked by pytest.
- [x] 4.2 Regenerate OpenAPI and the TypeScript client for the new profile IDs and stop code, and give the web app's copy for the new stop code. Checked by `contract_drift` in the fast profile and the web unit tests.

## 5. Docs

- [x] 5.1 Add the owner's `llama-server` section to `docs/engineering/runbooks/local-app.md`: the release check, `verify-models.py`, the start command bound to 127.0.0.1 with the profile's `--alias`, and stopping it. Checked by reading it against Decision 0041 A4 and A5.
- [x] 5.2 Amend `AGENTS.md`'s "Boundaries that matter", `.claude/rules/model-gateway.md` and the `autobots-model-gateway` skill. Checked by reading them against Decision 0041, and by the harness profile.
- [x] 5.3 Amend PRD-Model-Providers MP-02, MP-07's spend and MP-08, option-b-contract SP-008's budgets, PRD-Local-Mac-Deployment LM-01, LM-A03 and LM-07, and PRD-LangChain-Deep-Agents' scope, 2.2 and 6.3. Checked by reading each against Decision 0041 A2 to A4 and A15.
- [x] 5.4 Update `CODEBASE.md`'s model path and integration points, keeping `Analyzed revision` honest. Checked by reading it against the code.

## 6. Checks

- [x] 6.1 The fast profile passes for what changed, and the harness profile passes. Checked by `scripts/verify.py`.
