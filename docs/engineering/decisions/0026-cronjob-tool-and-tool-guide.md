# Decision 0026: The `cronjob` tool, and a tool guide in a modal

**Date:** 2026-11-08. **Authority:** the owner. They asked for:

- "Automation | cronjob | Scheduled tasks with create/list/update/pause/resume/run/remove actions."
- "On tool click open a modal with inputs and outputs and its why, when and what for that tool."

The design choices are made under their standing delegation. This adds to [PRD-Tool-Catalog](../../../PRD-Tool-Catalog.md) (sections Automation and Tool guide) and schedules US-14.19 and US-14.20.

The same request asked why the workflow preview didn't work. The preview loaded, but rendered under the list, below the fold, and its link doesn't scroll. That was fixed in the same session, without a story: choosing a workflow now brings its preview into view and focuses its heading.

## `cronjob`

A cron job here is an existing routine (US-7.1): a schedule that starts an Expert's goal or a published workflow version. The tool lets an agent manage the workspace's routines through the same service the Routines API uses. It adds no second scheduler.

| # | Choice |
|---|---|
| **C1. One tool, seven actions** | `cronjob` v1 takes `action`: `list`, `create`, `update`, `pause`, `resume`, `run` or `remove`.<ul><li>`list` takes nothing more.</li><li>`create` takes a `name` and a routine config (target, trigger, timezone, goal, inputs, tools, budget).</li><li>`update` takes a `routine_id`, its `expected_version` and the new config.</li><li>The other four take a `routine_id`.</li></ul>Every action stays in the run's workspace |
| **C2. Group and class** | The new group **Automation** ("Scheduled tasks that start goals and workflows"). Provider `autobots`, operation class `reversible_internal_write` with receipts, `free_local`, no network |
| **C3. Approval** | `list` runs without approval. Every other action can start or change paid work, so it waits for a person's approval, which shows the action, the routine and its schedule. Approval is per call and bound to the call's arguments, as for any effect |
| **C4. Grant** | Expert-only, like `browse_goal`: a run with no Expert behind it is refused `expert_grant_required`. Plain goals and workflows never get it |
| **C5. Same rules as the Routines API** | `create` and `update` go through the routine service's validation: its target must exist in this workspace, the run's tools can't exceed the target's, the budget is capped and the trigger and timezone are checked. A refusal keeps the service's typed code. `pause` and `resume` set `enabled`. The routine records the run's starter as its creator |
| **C6. `run`** | Admits one occurrence now, through the same admission as a scheduled one: overlap is skipped, and a missing key or offer blocks it. It returns the run id, or why it was skipped or blocked |
| **C7. `remove`** | Removing marks a routine removed (migration 53, `removed_at`). It is disabled, hidden from lists and never evaluated, and its versions, occurrences and runs are kept. Its name can be reused. Nothing is deleted |
| **C9. Approval in the catalog** | A descriptor's `approval` gains a third value, `by_action`, beside `always` and `never`. `cronjob` carries it, and the Tools page shows "Some actions wait for approval" |
| **C10. Removed or paused** | An action that names a removed routine is refused `routine_not_found`, as if it didn't exist. `run` on a paused routine is refused `routine_paused`, so a person resumes it first. In C6, "blocked" means no usable key for the workspace, or a model that isn't offered |
| **C8. What's shown** | Public fields are `action`, `routine_id`, `name`, and the outcome's `routine_id`, `status` and `run_id`. A goal's text and inputs stay out of the tool-use record |

## Tool guide

| # | Choice |
|---|---|
| **G1. What, when and why** | Every tool carries a guide with three short texts, and the catalog contract gains a `guide` object with all three:<ul><li>**What** it does.</li><li>**When** to use it.</li><li>**Why** it's useful.</li></ul>The texts describe; they grant nothing, and are never a value or a secret. A shipped tool without a guide fails a test. A test fixture's tool, which ships nowhere, reads "Not described yet.", so it never breaks the catalog it is checked through |
| **G2. Modal** | On the Tools page, choosing a tool opens a modal dialog. It shows the tool's title, availability and repair, then What, When and Why, then its inputs and outputs, each with name, type, required and whether it is shown in records. It replaces the side panel. The modal keeps everything the panel had: its URL (`?tool=<id>`), Granted to, Copy schema and the link to the full detail page. Escape, the Close button and a click outside close it, and focus returns to the tool's link |
| **G3. Accessibility** | A native `dialog` element, labelled by the tool's title. The focus trap is the browser's. It passes axe in both themes |

## What this doesn't establish

No routine is created on the persistent install and no paid run is started. Tests use disposable databases and a scripted model, or none.
