# Proposal

## Why

US-18.1 in SPECS.md: [Decision 0036](../../../docs/engineering/decisions/0036-inflation-rates-removed.md#decision) R1 to R7. The owner asked to remove the inflation tool and its World Bank code from Autobots, after a Market watcher run found the World Bank Indicators API unanswering. Removing a tool outright would break saved work:
- a saved Expert version or routine naming it raises when it becomes a grant;
- the editor carries the name into every revision, which is then refused;
- every run that isn't terminal recorded the whole tool map, so each one stops as `incompatible_version`.

## What Changes

- **BREAKING: `inflation_rates` and `world_bank` go (R1).** The tool's adapter, contracts, guide and grant entries, its `TOOL_VERSIONS` entry and pinned schema digest, and its tests are removed, along with the `world_bank` provider. OpenAPI and the TypeScript client lose `world_bank`. `market_history` is unchanged.
- **Retired tools (R2).** Autobots lists the tools it has retired, starting with `inflation_rates`. A check keeps any retired name out of the registry, the grant maps and `TOOL_VERSIONS`.
- **Grants skip a retired tool (R3).** An Expert's run in a session, a routine's run and a workflow's agent steps are granted the saved configuration's other tools. No stored configuration is rewritten.
- **Revisions drop it (R4).** A revision naming a retired tool is saved without it. Any other name the catalog doesn't hold is still refused with `expert_tool_not_available`.
- **Runs in flight (R5).** The execution-contract check accepts a recorded tool that is retired, so a paused run continues:
  - its model's tool list leaves the tool out;
  - a call to it is refused with `tool_not_registered`, and the model reads the refusal.

  A recorded tool removed without being retired still stops a run.
- **History (R6).** Earlier tool-use rows naming `inflation_rates` still read as recorded.
- **The seed (R7).**
  - The Market watcher tracks prices and exchange rates, without `inflation_rates`.
  - "Monthly FX and inflation note" becomes "Monthly FX note", with the step "Pull the rates" and an input for the currency pairs.
  - What already exists by name is kept.
- **Documents.**
  - PRD-Tool-Catalog TC-03 and "Market data";
  - PRD-Studio SD-01 and SD-02;
  - Decision 0017's Amended section;
  - the seeded workflows in `README.md`;
  - `CODEBASE.md`.

## Capabilities

### New Capabilities
- `retired-tools`: the list of retired tools and what each saved shape does with one: the catalog, grants, revisions, runs in flight and history.

### Modified Capabilities
- `market-data`: the inflation requirement is removed.
- `experts`: the concept seed's scenario names "Monthly FX note", and a requirement covers the seed's Market watcher and monthly workflow on new and earlier-seeded workspaces.

## Impact

- **Python:**
  - `adapters/market_data.py` and `contracts/market_tools.py`;
  - in `domain/`: `tools.py` (the retired list), `execution.py`, `tool_catalog.py` and `tool_guides.py`;
  - `contracts/tool_catalog.py`;
  - in `application/`: `experts.py`, `routines.py` and `workflow_executions.py`;
  - `operations/concept_seed.py`;
  - tests under `services/agent/tests`;
  - checks under `tests/db/checks`.
- **Contracts:** `contracts/generated/openapi.json` and `packages/api-client/src/generated.ts` lose `world_bank`. A request filtering the catalog by `provider=world_bank` is refused as an unknown value.
- **Web:** the provider labels in `apps/web/lib/tools/text.ts` and their unit test.
- **No migration and no paid call.** No stored row is rewritten.
