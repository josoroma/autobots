# Runbook: first durable goal-to-artifact slice

## Scope

Exercises one goal from admission to a verified artifact on disposable local services, with a scripted model. It proves the mocked slice of US-4.8, not a real provider, a real worker supervisor or H1.

## Run it

Needs the prepared environments from [the toolchains runbook](toolchains.md), the pinned Chromium from [the local app runbook](local-app.md) and Docker.

```sh
python3.12 scripts/qualify_identity.py
```

Expected: exit 0, and `PASS: browser:` lines for each test in `apps/web/tests/browser/slice.spec.ts`. It creates its own disposable stack and removes it. Other Docker resources stay untouched, and the script says so in its last lines.

## What the flow does

1. Signs in through the real form, saves an arranged key against a fake upstream, and admits `slice-complete` through the API with a document holding numbers chosen for this run, and a required artifact stating their total.
2. `tests/web/fixture_worker.py` claims the job and plans it, reads the document given at admission, sums what it read with the calculator and saves the report from that result. It then kills itself with SIGKILL inside a model call.
3. Its lease expires by database time. The restarted worker classifies the open call as uncertain and pauses the run, which the browser shows. Resume is refused at this point.
4. The test reports a charge as the owner, and resumes. The worker continues from its checkpoint, publishes, completes the task and verifies.
5. The browser shows `succeeded`, passed verification and one `report.md`. The test downloads it, and reloads to confirm the timeline replays with no gap or duplicate.

The other tests fail a run for a missing required artifact, a failed content check and an answer with no plan.

## If it fails

The failing line names the case. `.checks/identity/playwright.json` has browser errors, and `.checks/identity/results` has their traces, both ignored. A stack left by an interrupted run is named `autobots-disposable-*`, and the next run refuses nothing of yours. Remove only stacks with that marker, following [the local Supabase runbook](local-supabase.md).
