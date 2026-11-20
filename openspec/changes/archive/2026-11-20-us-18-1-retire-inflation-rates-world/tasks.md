# Tasks

## 1. Removal (The catalog no longer offers it)

- [x] 1.1 Remove `inflation_rates`, keeping `market_history`'s version, schema and digest:
  - its adapter, contracts and guide;
  - its `PROVIDER_TOOLS` and `TOOL_VERSIONS` entries;
  - its pinned digest and its tests;
  - `world_bank` from `ToolProvider` and the provider Literal.

  Checked by pytest under `services/agent/tests`: registry–catalog parity, the execution contract and the pinned schema digests.
- [x] 1.2 Regenerate OpenAPI and the TypeScript client without `world_bank`. Checked by `contract_drift` in the fast profile
- [x] 1.3 Remove `world_bank` from the web's provider labels and their unit test. Checked by the web unit tests under `apps/web/tests/unit`

## 2. The retired list (A retired name stays retired)

- [x] 2.1 `RETIRED_TOOLS`, `without_retired` and `retired_in` in `domain/tools.py`, and a test that no retired name is registered, in a grant map or in `TOOL_VERSIONS`. Checked by pytest under `services/agent/tests`

## 3. Saved work (A revision drops it; Saved Experts and routines still run; A workflow's agent step still runs)

- [x] 3.1 Expert create and revise drop a retired name before validation, and still refuse an unknown one with `expert_tool_not_available`. Checked by pytest and `retired_tools_check` in the db profile
- [x] 3.2 Expert binding and routine runs grant `without_retired` of the saved tools, and rewrite no stored configuration. Workflow agent tools stay filtered. Checked by `retired_tools_check` in the db profile

## 4. Runs (A run in flight carries on; A tool removed without being retired still stops a run; History stays as it was)

- [x] 4.1 `incompatibility()` skips a recorded retired tool, and a non-retired missing tool still blocks. Checked by pytest under `services/agent/tests`
- [x] 4.2 `retired_tools_check` covers the run cases, with a scripted model:
  - a paused run whose recorded contract and grant list `inflation_rates` v1 resumes and is claimed;
  - its model isn't shown the tool, and its call is refused `tool_not_registered`;
  - a run with a non-retired missing tool is refused and stopped;
  - an earlier `inflation_rates` tool-use row still lists as recorded.

  Checked by the db profile.
- [x] 4.3 `web_tools_check` exercises the metered limit with `market_history` only, and `browse_goal_check`'s provider set loses `world_bank`. Checked by the db profile

## 5. The seed (The seed on a new workspace; The seed on a workspace seeded before)

- [x] 5.1 The Market watcher without `inflation_rates`, and "Monthly FX note" with its "Currency pairs" input and its "Pull the rates" step, keeping what exists by name. Checked by pytest on the seed's definitions and by `concept_seed_check` in the db profile, on a new workspace and on one seeded with the old definitions

## 6. Documents

- [x] 6.1 Amend these as Decision 0036's "Requirements revised" lists:
  - PRD-Tool-Catalog TC-03 and "Market data";
  - PRD-Studio SD-01 and SD-02;
  - Decision 0017's Amended section.

  Also update `README.md`'s seeded workflows and `CODEBASE.md`. Checked by reading each against Decision 0036 R1, R5 and R7.
