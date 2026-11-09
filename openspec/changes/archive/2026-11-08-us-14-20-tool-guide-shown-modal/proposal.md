## Why

US-14.20, [Decision 0026](../../../docs/engineering/decisions/0026-cronjob-tool-and-tool-guide.md) G1 to G3, and PRD-Tool-Catalog TG-01 and TG-02. The owner asked that clicking a tool open a modal with its inputs and outputs, and say why, when and what for that tool.

## What Changes

- Every tool gets a guide of three short texts: what it does, when to use it, and why it's useful. They live in `domain/tool_guides.py`, keyed by tool id, for every registered and planned tool, `cronjob` included.
- The catalog contract gains a `guide` object with `what`, `when` and `why`. A unit test fails, naming the tool, when a guide is missing or a text is empty.
- On the Tools page, choosing a tool opens a native `dialog` modal instead of the side panel, keeping `?tool=<id>`. The modal holds:
  - the title and availability, with the repair when a tool is unavailable;
  - What, When and Why;
  - the Inputs and Outputs tables, with name, type, required and whether each field is shown in records;
  - Granted to, Copy schema and a link to the full page.
- The modal closes on Escape, Close or a click outside, and focus returns to the tool's link.

## Capabilities

### New Capabilities

- `tool-guide`

### Modified Capabilities

None.

## Impact

- **Backend:** `domain/tool_guides.py` (new), `application/tool_catalog.py`, `contracts/tools.py` and the regenerated client.
- **Web:** `apps/web/components/tool-catalog.tsx`.
- **Tests and docs:** the Tools browser suites, unit tests and CODEBASE.
