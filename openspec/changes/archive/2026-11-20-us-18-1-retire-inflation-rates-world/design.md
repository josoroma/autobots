# Design

## The retired list

`domain/tools.py` gains `RETIRED_TOOLS`, a frozen set holding `inflation_rates`, and two pure helpers:
- **`without_retired(tools)`** returns the names in order, minus retired ones.
- **`retired_in(tools)`** returns the retired names a collection holds, for the check that keeps them out.

The list lives beside the grant maps because each grant site already imports from there. `domain/execution.py` imports it from `domain/tools.py`; both are domain modules, so the layering holds.

A name is retired only by being listed. A tool that is merely missing from `EXPERT_TOOLS` is still unknown, so a typo is still refused at save, and a run that recorded it still stops (R4, R5).

## Where a retired name is dropped

| Site | Today | With this change |
|---|---|---|
| Expert binding, `application/experts.py` | `EXPERT_TOOLS[tool]` for every saved name, which raises a `KeyError` | Only `without_retired(config.tools)` is indexed |
| Routine run, `application/routines.py` | Same index over the routine's or the Expert's tools | The tools pass through `without_retired` before the availability check and the grant |
| Workflow agent tools, `application/workflow_executions.py` | Already skips names outside `EXPERT_TOOLS` | Unchanged: a retired name is outside it |
| Expert create and revise, `application/experts.py` | `validate_config` refuses names outside `EXPERT_TOOLS` | The config passes through `without_retired` first. The command fingerprint stays over the request as sent |
| Run preview, `api/run_routes.py`, and a workflow step's tools, `application/workflow_overview.py` | Every saved name is listed | They list what a run is granted, so `without_retired` of the saved tools |

Stored configurations are never rewritten, and `read_expert_config` returns what was stored. So a version's history and the stored-shape fixtures still show `inflation_rates` (R2, R6).

## The execution contract

`incompatibility()` skips a recorded tool that is absent from `TOOL_VERSIONS` and listed in `RETIRED_TOOLS`. Every other missing tool still returns "<tool> v<n> no longer exists".

The run then resumes with its frozen grant, which may still list `inflation_rates`. That needs no new code:
- `visible_tools` and `ToolDefinitions.catalog` leave out a granted tool the registry doesn't hold;
- `tool_gateway.resolve` refuses a call to it with `tool_not_registered`, routed SHOW, so the model reads the refusal and carries on.

A plan task that names the tool is still within the run's `allowed_tools`, so plan validation is unchanged.

## The seed

- **The Market watcher:** its purpose is "Tracks prices and exchange rates, and explains what moved and why it matters", and its tools drop `inflation_rates`.
- **The monthly workflow:**
  - `_monthly` labels its input "Currency pairs" and its first agent step "Pull the rates";
  - it is named "Monthly FX note", described as "Name the currency pairs. Their rates are pulled into a short note."

The seed keeps anything that already exists by name, so a workspace seeded before keeps the old Expert and workflow, and gains "Monthly FX note".

## Checks

- **pytest:**
  - the retired list against the registry, the grant maps and `TOOL_VERSIONS`;
  - the helpers;
  - `incompatibility()` for a retired and a non-retired missing tool;
  - the schema-digest fixture without `inflation_rates@1`;
  - the seed's definitions.
- **db profile:** a new `retired_tools_check` on a disposable stack, with a scripted model and no provider request:
  - a revision that drops the retired name, and the refusal of an unknown one;
  - a session run and a routine run from saved configurations that name it;
  - a workflow agent step;
  - a paused run whose recorded contract lists it, resumed and claimed, with its call refused `tool_not_registered`;
  - a run with a non-retired missing tool still stopped;
  - an earlier tool-use row that still reads as recorded.

  `concept_seed_check` covers both seed scenarios. `web_tools_check` moves its metered-call case to `market_history`.
- **Contracts:** regenerated, with no `world_bank`.
