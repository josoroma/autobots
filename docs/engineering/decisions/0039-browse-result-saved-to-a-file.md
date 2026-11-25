# Decision 0039: A browse's typed result can be saved straight to a file

**Date:** 2026-11-25. **Authority:** the owner, with the rest by delegation.

The owner's own choice, "Yes, build it", on saving a browse's result straight to a file without the model retyping it. The session had reported that the install's one Transcript reader run read its page to the end and published nothing.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0035 to 0038. Where two options were close, the choice keeps today's behaviour, adds the least or is easier to reverse. The owner can change any of them under US-21.1.

This amends [Decision 0035](0035-browser-use-typing-and-transcripts.md) Y12 and Y14, and the PRD rows below. It schedules EPIC-21.

## Context

- **The run.** On 2026-11-25 the owner authorized one run on the box. Its `browse_goal` call ended `done` after 10 steps, with no bot check. Then the run failed `plan_incomplete`, with no file.
- **Why a long result can't be saved today.** `save_artifact` takes the file's content from the model, and a model reply is capped at 4,096 output tokens. A long result doesn't fit in one. Past 48,000 characters the result is offloaded too, and is read back 4,000 characters a page.
- **The box isn't the limit.** browser-use delivers a value its code already holds (`finish_from_repl`), so nothing there is retyped.

## Decision

| # | Choice |
|---|---|
| **V1. Version 4** | `browse_goal` version 4 is version 3 with one optional input, `save`, taken only with an `output_schema`. Versions 1 to 3 stay registered with their schemas unchanged (Decision 0029 F13). New grants take version 4. A run that pinned an earlier version keeps it |
| **V2. What `save` names** | `path`, under `outputs/`. A layout is optional: `items`, the name of a top-level property that is an array of objects; `line`, the text for one item; and `before`, the text above the items. `items` and `line` go together, and `before` needs both. `{name}` in `before` is a top-level property of the result, and in `line` a property of an item. Any other brace is text. A value that isn't text is written as its JSON, and an absent one as nothing. A `save` whose names aren't in the schema is refused as invalid arguments, before any container starts |
| **V3. The worker writes it** | When the call ends `done` and the result validates (Y12), the worker writes the file: every item, in order, one line each, as it came. The model types none of it, and can't drop, merge or reword a line. A line break inside a value becomes one space, and space at a value's ends is trimmed, so an item stays one line. A NUL, or half of a surrogate pair, can't be stored: the first is left out and the second becomes `?`. With no layout the file is the result as indented JSON |
| **V4. A run file like any other** | It is written in the run's own files, as a new version, under the run's lease and within its path grants. A path outside them is refused `resource_not_granted` before any container starts. `publish_artifact` publishes it. A browse keeps no receipt (Decision 0020), so the file's version is bound to the call's tool-use row in place of an operation |
| **V5. What comes back** | `saved_path`, `saved_version`, `saved_sha256`, `saved_items` (empty without a layout) and `saved_characters`, and no `result`, so a long one never reaches the model. The tool row shows the path and the item count, and never the file's text |
| **V6. When it isn't saved** | `not_saved` says why, and the result comes back as version 3's does: `no_items` when a layout's array is empty, `too_large` past a run file's 256,000 characters, and `lease_lost` when the attempt has ended or its use was never recorded. A call that ends any other way than `done` saves nothing, and `not_saved` is empty |
| **V7. A repeat browses again** | As today, a browse repeated after a crash browses again. It saves a new version, and an earlier one stays as it was. The output names the version the call wrote |
| **V8. The Transcript reader** | The seeded instructions save with `save`, then publish, and say never to retype a line. Its tools, its empty browse domains and its `box` browser are unchanged (Y14, [Decision 0038](0038-local-stealth-browser.md) Z14). The seed keeps what exists (Decision 0034 S1), so an Expert already seeded changes only when its owner saves a new version |
| **V9. Not in this decision** | Saving another tool's output, adding to an existing file, and layouts beyond V2. Each needs its own decision |

## Requirements revised

The story amends these in its own change:
- **PRD-Tool-Catalog AB-05** gains `save` (V1 to V7).
- **PRD-Studio SD-02:** the Transcript reader's row names V8.
- **Decision 0035:** Y12 gains V1 to V7, and Y14's instructions save as V8 says.

## What this gives up

- **The model's check of the text.** It sees the item count and the browse's summary, and reads the file back only if it asks.
- **Layouts.** One heading and one line per item. Anything else is JSON.

## What this doesn't establish

That any site opens, or that a browse reads a page completely. The checks use scripted models and scripted browses, or Decision 0018's qualification hosts, and reach no YouTube (Y18). Nothing here establishes H1 or product acceptance.

## Reversal

Grant version 3 again in `domain/tools.py`. Version 4 stays registered for runs that pinned it.
