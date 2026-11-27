# Tasks: US-23.3, the Model source setting in Settings → Models

## 1. Storage and the settings API

- [x] 1.1 Add migration `20261127000071_model_source.sql`: `model_source` (default `openrouter`) and `local_profile` on `app_private.model_policies`, with header lines. Regenerate the schema snapshot and row types, and set `SHIPPED_MIGRATIONS`. Checked by the harness migration-header test, `test_schema_release.py` and the db profile.
- [x] 1.2 Add `GET` and `PUT /v1/settings/model-source` with owner authority, an expected version, the roles refusal and the local profiles' states. Regenerate OpenAPI and the TypeScript client. Checked by pytest under `services/agent/tests` and `contract_drift` in the fast profile.

## 2. Resolution and admission

- [x] 2.1 Resolve every role to the Local default on Local, refuse run role overrides and saved workspace role overrides as `model_not_offered`, read no key in `run_intent`, and list only offered local profiles without OpenRouter's catalog. Keep OpenRouter's saved choices through a switch and back. Checked by pytest under `services/agent/tests`, and by a db check on a disposable target.

## 3. Dispatch after a switch

- [x] 3.1 Add `model_source_disabled` (SUSPEND), refused at bind and on each attempt before anything is sent. Show resume after a switch back, cancel, and a linked new run admitted on Local. Checked by pytest under `services/agent/tests` and the db check.

## 4. Nothing to OpenRouter, and browsing

- [x] 4.1 Show a Local run end to end with no key, a fake local server and a fake OpenRouter transport that fails if touched. Show the admitted endpoint answering on the frozen local `researcher` route, still refusing an image. Checked by pytest under `services/agent/tests`.

## 5. Limits per route

- [x] 5.1 Add `limits_for` per profile, applied by `bind` to the loop's limits and call time, the request's output cap and the local client's timeout. Show the run budgets projection reading them. Checked by pytest under `services/agent/tests`.

## 6. Web

- [x] 6.1 Add the runtime health check, with its SHA-256 cached off the event loop, and the readiness service on Local. Checked by pytest under `services/agent/tests` with fake transports.
- [x] 6.2 Add the Model source panel above the provider panel, the disclosure following the source, and Home's local model words. Checked by the web unit tests, and by the db profile's browser suites, which keep passing on OpenRouter.

## 7. Docs and checks

- [x] 7.1 Amend the rows Decision 0041's "Requirements revised" lists for the setting: PRD-Model-Providers' introduction, MP-01, MP-04, MP-05 and MP-07; SP-006, SP-007 and SP-008's limits; LM-06 and LM-A06; BM-01 and BM-03; HM-05 and MD-01; and Decision 0019 S2 and Decision 0035 Y7 by notes in Decision 0041. Update the runbook's settings section, `README-DEV.md` and `CODEBASE.md`. Checked by reading each against A1, A7, A8, A10, A11 and A13.
- [x] 7.2 The fast, db and harness profiles pass. Checked by `scripts/verify.py`.

## 8. From verify

- [x] 8.1 Observe the composer's disclosure, Home's model chip and the panel on Local: the owner switches to Local, the disclosure says nothing goes to OpenRouter and that tool calls still leave the Mac, the model line says it's served on this Mac, Home says the local model isn't running, and the owner switches back. Checked by the db profile's browser suite (`models.spec.ts`).
- [x] 8.2 Show that on Local `run_intent` answers ready without reading any key. Checked by pytest in `tests/test_model_source.py` with a credential store that fails if read.
