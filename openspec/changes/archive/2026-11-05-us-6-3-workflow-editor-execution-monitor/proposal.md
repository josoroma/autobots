## Why

An automation builder needs to validate, publish and inspect a graph without leaving the app. PRD 12.1 and SP-014 require typed errors, version binding, node-instance status and emissions, and a monitor that is a projection, not a second scheduler.

## What Changes

- `/workflows` and `/workflows/[id]`: create, edit a graph, validate with typed errors, publish, choose a version and run it.
- `/workflow-executions/[id]`: exact binding, node-instance status and output emissions, read from saved rows.
- `GET /v1/workflow-blocks` and `GET /v1/workflow-executions/{id}`. An execution with an agent step needs a usable key.

**Limits:** the graph is edited as JSON, with a table of blocks and typed ports alongside. There is no visual canvas, which the sources describe only as a surface. The monitor polls once a second rather than using the event stream, since instance changes aren't public events yet.

## Capabilities

### New Capabilities

- `workflow-screens`: the workflow editor and execution monitor.

### Modified Capabilities

None.

## Impact

New screens, routes, contracts and a browser spec, `workflows.py`, the app shell, `CODEBASE.md`. No dependency or model call.
