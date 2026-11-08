## Why

US-16.5 carries out [Decision 0023 E6](../../../docs/engineering/decisions/0023-install-current-and-real-examples.md#decision). The owner asked for real examples of workflows, Experts, runs and approvals in their app, like the Studio concepts. Concepts used sample data; the app must show only what the system really did (Decision 0022 D1).

## What Changes

- **`persistent_install.py examples --project autobots-install --paid`**, beside `goal` and with its guards:
  - it reserves US$0.45 from the shared US$1.00 ledger before anything is sent;
  - it refuses while other work is queued or a routine is enabled;
  - it signs in as the owner from the install's record and saves the key to the workspace only if none is active;
  - a watchdog kills the worker if committed spend passes the reservation;
  - it scans stored rows and logs for the key afterwards.
- **What it makes, in the owner's workspace:**
  - the concept seed of US-15.25: five Experts and six workflows, keeping anything already named the same;
  - one goal run on Terra, limited to US$0.10;
  - one goal run with the Brief writer Expert on Sol, limited to US$0.10;
  - one execution of the published Vendor due diligence workflow for one vendor, with a US$0.25 budget, which stops at its approval gate. The approval is left pending for the owner.
- **One worker with inference on**, for this command only, stopped when the goal runs end and the workflow waits or ends.
- **`install-current.spec.ts`** gains a read-only check that Experts, Workflows, Runs and Approvals show them, through `persistent_install.py screens`.

- **Found by the first live attempt:** under Sol, and in the workflow's delegated Research analyst step on Terra, `propose_plan` cited a criterion by its text (`"c1: Explain…"`) and turned the opening's delivery step into a criterion, so the plan was refused as `plan_out_of_scope` twice and the run failed. A refusal names only a code, by design, so the model couldn't correct it. The system prompt, the opening and the `criteria` field's schema description now say a plan cites the listed criterion IDs and nothing else, and that the delivery lines are steps. Validation is unchanged.

- **Also found live, and decided under the owner's delegation (Decision 0023 E7):** verification needs every run to publish a file, a workflow's delegated step included, but SD-02 gave Market watcher and Research analyst only `save_artifact`. Both now also get `publish_artifact`, in the seed and in SD-02. On the install, the command adds it to the two seeded Experts through one new version each. A goal that already succeeded isn't run again, and the example vendor item says what to research and save, since each list item is the research step's whole goal.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `persistent-install`: real examples on the install.

## Impact

- `scripts/persistent_install.py`, `apps/web/tests/browser/install-current.spec.ts`.
- `services/agent/src/autobots/application/goal_loop.py`, `contracts/plans.py`, `tests/test_plans.py`.
- The persistent install's owner workspace, and up to US$0.45 of OpenRouter spend from the shared ledger.
