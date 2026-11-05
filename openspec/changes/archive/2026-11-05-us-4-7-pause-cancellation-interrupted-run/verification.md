# Verification — us-4-7-pause-cancellation-interrupted-run

Change: us-4-7-pause-cancellation-interrupted-run
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `dddb205`, working tree with this change. Real Postgres through the runtime role on a disposable target, a real Deep Agents graph with a scripted model, and real processes for death and sleep. `scripts/app_db.py types`: 305 cases passed. `scripts/qualify_identity.py` exit 0, 99 cases. `--profile full` passed.

## Scenarios

**Cancel any nonterminal run: observed.**
- Queued, waiting for input, waiting for approval and paused cancel directly. Running and verifying with a live owner enter `cancelling`. Cancelling again changes nothing.
- After a cancel, a worker's complete, verify and request-input commands are refused, and the owner finishes it.
- A dead owner with a dispatched call enters `cancelling`, not `cancelled`. Recovery classifies the call `uncertain`, finishes as `cancelled_with_unknown_outcomes`, and keeps its reservation. That outcome stays visible after the run is terminal, and a later charge updates the evidence without reopening the run.
- A cancel arriving during a model call stops the next dispatch: `cancelled`, 2 calls, no file. A tool result arriving after a cancel is recorded in its receipt and refused.
- Twenty rounds of concurrent completion and cancellation: one winner each, 14 succeeded and 6 cancelling, and none did both.

**Resume only paused work: observed.**
- A run waiting for input was paused and resumed. It re-entered `queued`, and the next worker went back to `waiting_input` with no model call and one open obligation. Answering met it and the run continued.
- A changed workspace default left the run's frozen policy snapshot as it was. A route differing from the snapshot gives `route_not_bound` with no call.
- Through the API: with the key disconnected, resume is refused with `credentials_required`, and it succeeds once a key is back.
- Resume, input and pause can't reopen a terminal run. Continuing takes a new run with `continues_run_id`, the old one stays `cancelled`, and a nonterminal or other-workspace run is refused.

**Recover after sleep or loss: observed, with SIGSTOP standing in for Mac sleep.**
- A real worker with a 2-second lease was stopped with SIGSTOP inside a model call. It stopped renewing, and its lease ran out.
- A replacement classified the call `uncertain` and paused with `uncertain_model_call`, with no new model call.
- After SIGCONT, the old worker reported `lost`, wrote no status, and the replacement's decision stood. Its late response reconciled the charge, recorded as 100.
- Resuming then allowed another paid dispatch. An unreconciled uncertain call blocks another dispatch, and blocks resume through the API.
- US-4.3's killed-process case now goes through this: classified, paused, reconciled by hand, resumed, and finished from its checkpoint as generation 3.

## Findings

- **Fixed in US-4.3's code:** a lease was never renewed during a loop, so a long call would have lost it. `run_goal` now heartbeats on its own connection. Slots held by a dead worker, which US-3.3 left open, are now released when recovery classifies the call. That release only happens once a replacement runs.
- **An owner reconciles by stating a charge,** through `POST /v1/runs/{id}/model-calls/reconcile`. It records what the provider's account shows, for the oldest open call. There's no UI, and no automatic read from OpenRouter, since no generation ID is stored yet.
- **SIGSTOP isn't real sleep.** Real wake detection, rechecking services on wake and `reconcile_run` on a timer aren't built. A worker only reconciles artifacts when it's given a store.
- **Not built:** cancellation propagating to children, since none exist. Process supervision. The 1-second cancellation and 60-second recovery targets aren't measured.
