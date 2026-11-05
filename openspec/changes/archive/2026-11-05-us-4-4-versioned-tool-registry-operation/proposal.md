## Why

A model must not bypass scope through SDK or MCP tools. SP-013 and PRD 9.1 require one enforcement layer, with versioned contracts checked before effects and durable identity for effects.

## What Changes

- `application/tool_gateway.py`: registry and gateway. Grants pin versions. Schema, resources, run status and ownership are checked before an effect. Effects commit a `started` receipt first, reuse it on replay, and report `unknown` rather than repeat.
- `application/tools.py`: `calculate`, `read_run_file` and `save_artifact` over virtual run files.
- `adapters/tool_middleware.py`: answers every tool call in a Deep Agents loop from the gateway and shows the model only granted tools.
- A migration for `tool_receipts` and `run_files`.

**Limits:** consequential writes are always refused until US-5.3's approvals exist, and arbitrary execution can't be registered. `run_files` are database rows, and private storage is US-4.5. MCP tools have no adapter, so here they are only denied by name. The loop itself is US-4.3.

## Capabilities

### New Capabilities

- `tool-gateway`: versioned tools, an enforced boundary and durable operation receipts.

### Modified Capabilities

None.

## Impact

A migration, new domain, contract, application and adapter modules, DB and unit tests, `scripts/app_db.py`, `CODEBASE.md`. No dependency or paid model call.
