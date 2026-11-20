# Design

## Context

See proposal.md, Why. `public.workflows.name` is a plain column with `check (char_length(name) between 1 and 100)` and `unique (workspace_id, name)`, which only `autobots_runtime` may update. `set_description` is the model for a write that changes no version: one `update ... returning id`, behind `OwnerWorkspace`, with no key. The concept seed creates a workflow under the key `concept-seed:workflow:<name>` and publishes it under `concept-seed:publish:<name>`, and a receipt replays the workflow it first created for as long as receipts are kept.

## Goals / Non-Goals

**Goals:**
- One write that changes only the name, and whose refusals are typed, races included.
- A seed that never writes onto a workflow the owner renamed.

**Non-Goals:**
- A history of earlier names, and renaming Experts (Decision 0037, What this gives up).
- Changing how `create_workflow` checks a name.

## Decisions

- **The unique constraint decides, with no select first.** `rename_workflow` runs `update public.workflows set name = %s where id = %s and workspace_id = %s returning id` and turns `psycopg.errors.UniqueViolation` into `workflow_name_taken`. The name is the only unique column the update touches, so the violation can only be the name. A select before the update would still lose a race, and add a round trip. Renaming to the workflow's own name updates the row to the same value and violates nothing, so it succeeds with no special case. No returned row means the workflow is not this workspace's: `workflow_not_found`, as for the description.
- **The contract repeats creation's field.** `WorkflowRename.name` is `Field(min_length=1, max_length=100)`, the same as `WorkflowCreate.name`, so the API refuses an empty or over-long name as `invalid_request` before the database is reached. The editor trims, and sends nothing for a blank name. The API keeps creation's rule and trims nothing, so a name the API accepts at creation it accepts at rename.
- **`PUT` with no key**, like the description (N5). Sending the same name again gives the same result, so a lost reply is retried by pressing again.
- **The seed follows its receipts to a workflow under the seeded name.** After `create_workflow` returns, a view whose name is not the seeded one means the receipt replayed onto a workflow since renamed. The seed then creates again under `concept-seed:workflow:<name>:beside:<that workflow's id>`, and repeats while the result was renamed too. Each key is fixed by what it follows, so seeding again is still repeatable, and it ends, since each step either creates a workflow or follows a receipt to a different one. The publish key becomes `concept-seed:publish:<workflow id>`, so publishing the workflow beside never replays the renamed one's publish. A publish happens only right after a create in the same run, so no earlier seed's publish is replayed differently. The alternative, unseeding receipts or matching by id, would rewrite stored receipts or need a new table.
- **The editor's name field mirrors the description's.** It is a `use-name.ts` hook and a `name-field.tsx` field, sharing the editor's message line. Success says "Name saved. No version changed." `workflow_name_taken` is worded as creation words it, "That name is already used.", and `owner_required` as "Only the workspace owner can rename a workflow." A blank field says "A workflow needs a name." and sends nothing. The heading reads the view that `onSaved` hands back.

## Risks / Trade-offs

- [A long transaction holding a new name blocks a rival rename until it ends] → Each rename is one statement, so the wait is the length of one update. The loser then gets `workflow_name_taken`, which the race check arranges by holding the first update's transaction open.
- [A receipt that has expired under `receipt_days`] → The seed's name check comes first, so it is kept if its name is unchanged. A renamed one whose receipt expired gets the seeded workflow beside it, which is N6's outcome either way.
- [A run's goal keeps the old name, while its list label shows the new one] → This is N4, by decision, and the search still finds the run by the old name.

## Migration Plan

No migration. Deploying is restarting the API and the web. Reverting removes the route, the field and the seed's follow-on key, and workflows keep the names they were given (Decision 0037, Reversal).
