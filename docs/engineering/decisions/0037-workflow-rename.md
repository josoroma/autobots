# Decision 0037: A workflow's owner can rename it

**Date:** 2026-11-20. **Authority:** the owner, with the rest by delegation.

The owner's own choices:
- **The request:** "update it and rename it to Monthly FX note", for the workflow their install was seeded with as "Monthly FX and inflation note" ([Decision 0036](0036-inflation-rates-removed.md) R7), after the session reported that Autobots had no way to rename a workflow.
- **The scope:** "Add rename to the app", over running a database update themselves.

The rest are the session's choices, under the owner's standing delegation, as in Decisions 0031 and 0036. Where two options were close, the choice follows how the description is edited (PRD-Studio WF-06) and adds the least. The owner can change any of them under US-19.1.

This amends [PRD-Studio](../../PRD/PRD-Studio.md#workflows) WF-06, as below. It schedules EPIC-19.

## Decision

| # | Choice |
|---|---|
| **N1. Who** (owner) | The workspace owner renames a workflow from its editor. A member reads the name and is refused a rename with `owner_required`, as for the description |
| **N2. The name** | The rule for creating a workflow holds: 1 to 100 characters, unique within the workspace as stored. A name another workflow of the workspace holds is refused with `workflow_name_taken`, and nothing changes. Renaming a workflow to its own name succeeds and changes nothing. The editor trims what is typed and sends no blank name |
| **N3. Nothing else changes** | A rename changes no version, graph, hash, draft, description or execution. Runs, routines and executions bind a workflow by its id and version, so each keeps working as before |
| **N4. Where the new name shows** | Everything that reads the workflow when it is shown: the workflow list, preview and editor, the Tools page's "Granted to", and the runs list's label, which joins the workflow. A run's goal, "Workflow <name>, version <n>", was written when its execution started, so it keeps the name it ran under, and its search still finds the run by that name |
| **N5. The write** | `PUT /v1/workflows/{id}/name` with `{name}` returns the workflow's view. Like the description's write, it replaces the name whole and carries no idempotency key, since sending it again gives the same result. When two renames race for one name, the database's unique constraint decides, and the loser is refused with `workflow_name_taken` |
| **N6. The seed** | The seed keeps what exists by name ([Decision 0034](0034-deep-research-like-content-writer.md#seed-us-166) S1). A seeded workflow renamed away from its seeded name keeps its new name, and seeding again adds the seeded one beside it. A workflow renamed to a seeded name, as "Monthly FX and inflation note" to "Monthly FX note", is kept, and seeding again adds nothing for that name |

## Requirements revised

The story amends this in its own change:
- **PRD-Studio WF-06** becomes "Name, labels and description", and says that a workflow's owner can rename it, under N2 and N3.

## What this gives up

- **The earlier name.** Nothing records it, except the goals of runs started under it (N4).
- **Experts.** Renaming an Expert is not part of this.

## What this doesn't establish

Nothing here establishes H1 or product acceptance.

## Reversal

A new decision that removes the write. Workflows keep the names they were given.
