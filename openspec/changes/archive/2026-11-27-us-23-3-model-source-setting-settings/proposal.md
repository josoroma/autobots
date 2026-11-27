# Proposal: the Model source setting in Settings → Models (US-23.3)

## Why

Decision 0041 A1 gives each workspace a Model source: OpenRouter, as today, or Local, where every model call goes to offered local profiles served on this Mac. US-23.1 built the local route, and US-23.7 qualified Bonsai 2.5's, so a local profile can be offered. Nothing yet lets the owner choose Local, and every admission path still requires an OpenRouter key.

## What Changes

- **A stored Model source per workspace,** OpenRouter for every new and existing workspace. The OpenRouter default and role overrides are kept while Local is on, so switching back restores them. The Local default is its own value.
- **`GET` and `PUT /v1/settings/model-source`:**
  - Only the owner switches (MP-05; no admin role exists).
  - It takes an expected version, and the Host, Origin and CSRF checks apply through the BFF.
  - A switch to Local is refused, naming the roles that have no offered local profile: `executor`, and also `researcher` while any Expert grants `browse_goal` (A7).
  - Its state lists each local profile, offered or not with the reason, the runs it has matched (none yet), and the runtime's health. Health is the model ID served and whether the served file's SHA-256 matches the pin.
- **On Local:**
  - Every role resolves to the Local default profile, and the run freezes that route.
  - A workspace role override can't be saved, and a run that names a role override is refused `model_not_offered` (A8).
  - No OpenRouter key is read. Pickers list offered local profiles only, and nothing is sent to OpenRouter, its catalog included (A13).
- **`model_source_disabled` (A12).** A model call whose frozen route is on the source switched off is refused before anything is sent, at bind and on each attempt. The run waits with that reason until the owner switches back, cancels it, or continues it as a linked new run.
- **Limits per route (A11),** from Decision 0041's measurements table: a call's time, active time and output cap follow the run's frozen executor profile. OpenRouter keeps 300 seconds a call and 45 active minutes.
- **Web:**
  - A Model source panel above the provider panel and the model policy.
  - The composer's disclosure follows the source.
  - On Local, Home's model service reads "Local model ready" or that it isn't running.
- **Docs:** the PRD, contract and decision rows Decision 0041's "Requirements revised" lists for the setting, the local app runbook, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `model-source`: the workspace's Model source, switching it, resolution and admission on each source, the refusal at dispatch after a switch, limits per route, and what Settings, the composer and Home show.

### Modified Capabilities
- None. `model-policy`, `model-policy-settings`, `provider-settings` and `run-disclosure` keep their OpenRouter requirements, which still hold on OpenRouter.

## Impact

- **SQL:** one migration adding `model_source` and `local_profile` to `app_private.model_policies`. Existing rows read as OpenRouter.
- **Python:**
  - `application/model_policy.py`, `run_admission.py`, `provider_settings.py`, `worker_inference.py` and `local_offering.py`, plus a local runtime health check.
  - `domain/models.py` (route limits), `domain/stops.py` and `application/model_attempts.py` (`model_source_disabled`).
  - The API's model policy, provider, readiness and run routes, and their contracts.
  - OpenAPI and the TypeScript client are regenerated.
- **Web:** `app/settings/models/page.tsx`, a model source panel, the disclosure, readiness words, and their unit tests.
- **Docs:** PRD-Model-Providers, the Option B contract, PRD-Local-Mac-Deployment, PRD-Tool-Catalog, PRD-Studio, Decisions 0019 and 0035 (by amendment note), the runbook, `README-DEV.md` and `CODEBASE.md`.
