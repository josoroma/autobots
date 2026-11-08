# Decision 0023: A current install with real examples, workspace choice and sober controls

**Date:** 2026-11-08. **Authority:** the owner. In this session they asked for four things and delegated the choices: "in all the following goals and task take senior decision for me, i trust you security and taste". This record keeps their requests and the choices made under that delegation. It schedules EPIC-16.

## The owner's requests

1. Perform a real live qualification of `openai/gpt-6.1-sol-20260929`, shown at Settings → Models.
2. Close the two risks the refreshed `CODEBASE.md` recorded. Operations' schema check stops at migration 37 and never compares the applied count with the migration files, so a database missing newer migrations isn't shown as behind. A member of several workspaces gets "Choose a workspace", because no client says which workspace is meant.
3. Inputs get the same sober border as the other components, without the strong line at the bottom.
4. Leave real examples of workflows, Experts, runs and approvals in the app, like the [Studio concepts](../../imagine/README.md).

## What was found

The persistent install had applied 35 of 49 migrations, so it lacked Sol's profile and its 2026-11-07 qualification row. That's the "behind" case from request 2, live: Operations reported the schema ready.

## Decision

| # | Choice |
|---|---|
| **E1. Controls** | Input, Textarea and Select lose the inset bottom line. Each gets one even 1 px border on all sides, in a new `--control-border` token that's exactly as strong as DS-03's 3:1 non-text contrast needs, in both themes, and no stronger. The composer's goal field gets the same rounded border. Focus keeps its ring |
| **E2. Schema readiness** | The API carries the count and newest name of the migrations its release ships, and a check fails when they disagree with `supabase/migrations`. Readiness reports `schema_behind` when the database has applied fewer migrations than that, and `schema_ahead` (degraded, not blocking) when it has applied more. The relation and column lists also cover what migrations 38 to 49 add, for a database with no readable history |
| **E3. Workspace choice** | The chosen workspace is kept in an HttpOnly, SameSite=Strict cookie that only a same-origin, CSRF-checked route sets. The BFF sends it as `X-Autobots-Workspace`, and the API still checks membership on every request. There's no implicit default for a member of several workspaces: the sidebar asks them to choose, and the choice can be changed there. A member of one workspace sees nothing new |
| **E4. Bring the install current** | Before any change, a backup of the install through the backup runbook. Then the guarded `apply`, the only path that changes the persistent database. No reset, no volume removal. The project's hook keeps the install's record, keys and `app.env` out of the assistant's commands, so the owner runs the backup, apply and restart, as one reviewed script |
| **E5. Sol requalification** | One more full live pass of the US-3.4 corpus on Sol, inside the cap Decision 0019 S4 already authorized (US$1.20 for Sol's ledger, of which US$0.14 is committed). If it passes as it did on 2026-11-07, a migration records today's date and its findings, and Settings → Models shows them |
| **E6. Real examples** | On the persistent install's owner workspace: the concept seed (US-15.25), two small real goal runs and one real execution of a published concept workflow that stops at its approval gate. The approval is left pending for the owner to decide. Total spend is capped at US$0.45 from the shared US$1.00 ledger: each goal run is limited to US$0.10, and the workflow to US$0.25, the smallest budget a workflow execution allows (Decision 0022 D11). Nothing here is sample data: every run, plan, artifact and approval is what the system actually did |
| **E7. Experts that save also publish** | Found by E6's live runs: verification requires every run to publish a file, a workflow's delegated step included, but SD-02 granted Market watcher and Research analyst only `save_artifact`. So any concept workflow step using them could never pass. Both now also get `publish_artifact`, which publishes only the run's own file inside the app, so they stay read only by D14. This amends [PRD-Studio SD-02](../../../PRD-Studio.md#seed). The verification rule is unchanged. On the install, each of the two seeded Experts gets one new version that only adds the grant; earlier versions are kept |
| **E8. Plans cite criteria by ID** | Also found live: under Sol, and in a delegated step on Terra, `propose_plan` cited a criterion by its text and turned a delivery step into a criterion, so the plan was refused twice and the run failed. A refusal names only a code, by design. The system prompt, the goal's opening and the plan schema now say a plan cites the listed criterion IDs and nothing else, and the delivery lines are steps |

## What this doesn't establish

Neither the requalification nor the example runs establish H1, product acceptance or task quality. The examples are real but few, and the approval stays undecided.
