# Decision 0036: inflation_rates and the World Bank provider are removed

**Date:** 2026-11-20. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The request:** "no, remove Inflation or world bank code please", after a Market watcher run on their install found the World Bank Indicators API unanswering.
- **The scope:** "Remove it from the code", over leaving the tool in place and only revising their Experts.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0031 and 0032. Where two options were close, the choice keeps saved work readable and adds the least. The owner can change any of them under US-18.1.

This amends:
- [Decision 0017](0017-tool-catalog.md) C1, so that the World Bank Indicators API is no longer a tool provider, Q5, which no longer holds, and its Reversal, which R5 qualifies for a retired tool.
- [PRD-LangChain-Deep-Agents](../../PRD/PRD-LangChain-Deep-Agents.md#103-pause-cancel-and-resume) 10.3, whose resume keeps a run's tool revisions, which R5 qualifies for a retired tool.
- [PRD-Tool-Catalog](../../PRD/PRD-Tool-Catalog.md) TC-03 and "Market data", and [PRD-Studio](../../PRD/PRD-Studio.md#seed) SD-01 and SD-02's Market watcher and its monthly workflow, as below.

It schedules EPIC-18.

## Decision

| # | Choice |
|---|---|
| **R1. What goes** (owner) | `inflation_rates`, its World Bank adapter and contracts, its tool guide and the `world_bank` tool provider leave Autobots. `market_history` on Yahoo's chart endpoint stays as it is. No other inflation source replaces it |
| **R2. Retired, not unknown** | Autobots lists the tools it has retired, starting with `inflation_rates`, and never reuses a retired name for another tool. A saved Expert version or routine that names one keeps its stored bytes, and its history still shows the name |
| **R3. Granting skips it** | A retired tool is left out wherever a saved configuration becomes a grant: an Expert's run in a session, a routine's run, and the tools a workflow's agent steps bring. The configuration's other tools are granted as before |
| **R4. Saving drops it** | A revision that names a retired tool is saved without it rather than refused, so an Expert saved before the removal can still be edited from its last version. Any other name the catalog doesn't hold is still refused with `expert_tool_not_available` |
| **R5. Runs in flight** | Every run records the whole tool map at admission, so a removed tool would otherwise stop every saved run that isn't terminal. A retired tool doesn't: a paused or queued run continues, its model no longer sees the tool, and a call to it is refused with `tool_not_registered`, which the model reads before it carries on. A tool removed without being retired still stops a run, as before |
| **R6. History stays** | Earlier runs' tool-use records, artifacts, receipts and events stay as they were. Nothing rewrites a stored row |
| **R7. The seed** | The Market watcher tracks prices and exchange rates, with no `inflation_rates`. "Monthly FX and inflation note" becomes "Monthly FX note", whose step is "Pull the rates" and whose input names the currency pairs. The seed keeps what already exists by name (Decision 0034 S1), so a workspace seeded before keeps its Expert and workflow, and seeding it again adds "Monthly FX note" beside the old one |

## Requirements revised

The story amends these in its own change:
- **PRD-Tool-Catalog TC-03:** its providers lose `world_bank`.
- **PRD-Tool-Catalog "Market data":** loses the `inflation_rates` row, so the paragraph under it describes `market_history` alone.
- **PRD-Studio SD-01 and SD-02:** SD-01 names "Monthly FX note", and SD-02's rows for the Market watcher and the monthly workflow follow R7.
- **Decision 0017:** C1 names Tavily, Jina and Yahoo Finance's chart endpoint, Q5 no longer holds, and its Reversal's `incompatible_version` holds for a tool removed without being retired.
- **PRD-LangChain-Deep-Agents 10.3:** a resumed run keeps its tool revisions, except a retired tool, which a call meets as `tool_not_registered` (R5). It replays no checkpoint through changed semantics, since a retired tool has none left to run.

## What this gives up

- **No inflation figures from a tool.** A run that needs them reads a published source with the search and extraction tools, or a file a person attaches, and cites it.
- **Saved names that do nothing.** An Expert version saved with `inflation_rates` still lists it, and its runs simply don't get it. Revising the Expert clears it (R4).
- **A second monthly workflow** on a workspace seeded before, if the seed runs there again (R7).

## What this doesn't establish

Anything about the World Bank Indicators API. The timeout of 2026-11-20 was the occasion for the request, not a measurement of the service. Nothing here establishes H1 or product acceptance.

## Reversal

A new decision and a new tool, under a new name. The retired name stays retired, because saved Expert versions still name it (R2).
