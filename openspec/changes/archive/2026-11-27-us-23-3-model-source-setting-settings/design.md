# Design: the Model source setting (US-23.3)

## Context

- **Storage.** `app_private.model_policies` holds one row per workspace: `version`, `default_profile` (nullable) and `role_overrides`. It has no source.
- **Admission and key checks.**
  - `WorkspacePolicy.for_new_work` resolves MP-01's order and checks `OFFERED_FOR_NEW_RUNS`, which holds Terra and Sol only.
  - `ProviderSettings.run_intent` is every admission path's key gate: runs, resume, workflows, improvements, routines and the intent check.
- **The worker.**
  - `InferenceSource.bind` freezes the route from the run's snapshot, and `_refusal` skips local routes.
  - `open_attempt` branches on `is_local`. The browsing route goes through the same `AttemptModel`, so a frozen local `researcher` route already follows.
- **Limits are constants.**
  - `RootLimits` gives 2,700 active seconds.
  - `MODEL_CALL_SECONDS` is 300, but `LoopConfig.model_call_seconds` defaults to 120, and that default is what the worker passes to the loop.
  - `MAX_OUTPUT_TOKENS` is 4,096 for every route.
- **Roles.** There is no admin role: members are `owner` or `member`.
- **Stop codes** are free text, and an unknown one suspends.

## Decisions

### D1. Storage: two columns on the policy row

The migration adds:
- `model_source text not null default 'openrouter'`, checked to `openrouter` or `local`;
- `local_profile text`, checked to the two local profile IDs.

Existing rows read as OpenRouter. `default_profile` and `role_overrides` stay OpenRouter's and aren't touched while Local is on, so switching back restores them. A switch bumps the row's one `version`, which the model policy panel shares.

### D2. The source is derived from a run's frozen route

A run never mixes sources (A1), so its source is whether its frozen executor profile is local. Nothing new is stored in the policy snapshot.

The limits come from the frozen profile too: `domain/models.limits_for(profile)` returns:
- OpenRouter: 300 seconds a call, 2,700 active seconds, 4,096 output tokens and 64K context;
- Bonsai 2.5: 1,800 seconds, 14,400 active seconds, 4,096 tokens and 64K;
- Inkling 2 Mini: 1,800 seconds, 14,400 seconds, 8,192 tokens and 64K.

All keep Decision 0034 L2's 64 model calls and 96 tool dispatches. `bind` sets the loop's limits and call time from the route, so the worker's 120-second default no longer applies. The request's `max_tokens` and the local client's timeout (call time plus 30 seconds) follow the same profile.

### D3. Resolution on Local

`WorkspacePolicy` carries the source, the Local default and the offered local set. The offered set is read from `agent_runtime.route_qualifications` through `local_offering.offered_locally`.

On Local:
- every role binds to the Local default, or to a run-wide profile, which must itself be offered locally;
- any run role override is refused `model_not_offered` (A8);
- `run_intent` answers `ready` without reading a key;
- `PUT /model-policy` maps its default to the Local default, refuses any role override, and leaves OpenRouter's saved choices alone;
- reset changes nothing;
- `GET /v1/models` lists offered local profiles without fetching OpenRouter's catalog, and `GET /model-providers` reports its catalog as `unknown` without fetching it.

### D4. Switching

`PUT /v1/settings/model-source` takes `{expected_version, source, local_profile?}` and is owner-only (`OwnerWorkspace`).

A switch to Local:
- chooses `local_profile`, or else the saved Local default, or else the first offered local profile;
- is refused `model_source_roles_uncovered` (409) when no offered local profile exists, naming `executor`, plus `researcher` when the latest version of any Expert in the workspace grants `browse_goal`;
- is refused `model_not_offered` when a named profile isn't offered.

A stale version is `stale_version` (409), as for the model policy.

### D5. Refused at dispatch after a switch

`model_source_disabled` is a new `FailureClass` and SUSPEND `StopCode`. It is checked twice:
- in `bind`'s refusal, before anything reserves;
- in `open_attempt`, before each call, by reading the workspace's source.

So a call is refused before anything is sent to either source. The run pauses with that reason. After a switch back, resume binds again and calls go out on the frozen route.

A cancel ends the run. As today, a linked new run continues only an ended run, so the owner cancels and then continues it, and the new run is admitted on Local.

### D6. The runtime's health

`application/local_runtime.py` checks the owner's server for the Local default profile:
- `/v1/models` must report exactly its model ID: `ready`, `other_model` or `not_running`;
- `/props` gives the served file's path, whose SHA-256 is compared with the pin.

The hash is computed once per path, size and modification time, off the event loop in a background task, and reads `checking` until it's done. Settings shows `sha256_matches` as true, false or not known. Home's readiness uses only the model ID check, so it never waits for a hash.

### D7. Web

- `ModelSourcePanel` sits above `ProviderSettingsPanel`. It shows the radio for the owner (read-only for a member), each local profile's state and reason, matched runs ("None yet"), the runtime, the roles covered and the spend note.
- The disclosure's `DataNotice` and `ModelAndBudget` take the source.
- Readiness's model service reads "Local model ready" or "Local model isn't running" when the API reports the local service.

## Risks

- Hashing 7.5 GB takes seconds. It runs off the event loop once per file, and the page shows `checking` meanwhile.
- Matched runs stay empty until US-23.4 to US-23.6 record a match.
