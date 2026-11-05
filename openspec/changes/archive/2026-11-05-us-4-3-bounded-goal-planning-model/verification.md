# Verification — us-4-3-bounded-goal-planning-model

Change: us-4-3-bounded-goal-planning-model
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `c8a77df`, working tree with this change. A real `create_deep_agent` graph, real Postgres checkpoints and real model admission on a disposable target, with a scripted fake model. No real model has run this loop. `scripts/app_db.py types`: 263 cases passed. `scripts/qualify_identity.py` exit 0, `--profile full` passed.

## Scenarios

**Preserve goal and evidence through planning: observed with a scripted model.**
- A goal with two criteria went through a plan, a save, a completed task, a revision with a reason, more work and completion. The result was `candidate`, and the run moved to `verifying`.
- The original request and criteria are unchanged. Plan rows are v1 with no reason and v2 with `the figures need a table`, and v1's title is still stored. Evidence for the task completed before the revision survives it.
- A plan naming a new criterion is refused with `plan_out_of_scope`, and a repeat spends the one repair. Unit tests also refuse a new tool, a dropped criterion, a dropped or rewritten completed task, a missing reason, cycles and unknown dependencies.
- Completion comes from recorded evidence. "Finished, trust me" with open tasks gives `plan_incomplete` and `failed`, listing what remains. No plan gives `plan_missing`. Invented evidence gives `evidence_invalid`, and open dependencies give `task_dependencies_open`.

**Stop within root limits: observed with a scripted model.**
- Model calls: limit 2 gave `model_calls_limit`, the model called twice, and the refused attempt left nothing dispatched.
- Tools: limit 2 gave `tool_dispatches_limit`, reporting plan v1 and the one file that was really saved.
- Time: a zero limit gave `active_time_limit` with no calls. Plan revisions: the third gave `plan_revisions_limit` at v3.
- Repair: invalid arguments twice stops after 2 calls. Once is repaired, and the work finishes. Truncated output never runs its tool calls, gets one repair with a note, then stops with `incomplete_output`.
- Children: `task` and `execute` get no capability through the loop. `children` is only a counter, which refuses a fifth, since no child execution exists.
- Retries count: three provider errors use 3 of the budget and stop.
- Waiting cases pause instead of failing: a rejected credential after one attempt, a call past the budget with no dispatch, and an uncertain call that keeps its reservation and isn't sent again.
- Restart: a real worker process killed with SIGKILL inside its third model call left its job claimed and the call open. After an arranged lease expiry and a hand-closed invocation, the replacement resumed from the checkpoint, with earlier tool results in its prompt, usage 3 then 6, and no second file.
- A worker that loses its lease reports `lost`, and writes no status.

## Findings

- **Deep Agents can call the model on its own,** through its summarizer. `AdmittedModel` refuses any call outside an admitted dispatch, shown directly. A summarization trigger inside a real loop was not reached, so what the SDK does with that refusal isn't observed.
- **A dead worker leaves its model call `dispatched`,** holding a slot. The check closed it by hand. US-4.7 owns that reconciliation.
- **No real provider has run this.** `_charged` reads `response_metadata["cost"]`, from reading the SDK's source. Real failures map through `status_code` or become uncertain, which stays unverified until paid qualification, US-3.4.
- **Not built:** 8K context and 512 output limits, the 80% warning event, pausing on a run from a real pricing estimate (the caller supplies worst-case cost), and child execution. `stop_reason` isn't in a public event yet, which US-4.6 can project. `paused` for `no_inference_slot` and the default criterion, when a request names none, are my reading.
- **Scope of this change:** `apply_command` has a new `suspend` worker command, because SP-010 allows a pause from `running` and the existing one was user-only.
