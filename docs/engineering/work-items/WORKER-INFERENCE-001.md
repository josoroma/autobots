# WORKER-INFERENCE-001 — Inference step in the product worker

Status: COMPLETE, as built, on mock and disposable evidence only
Evidence: [US-11.12's manifest](../evidence/US-11.12/gate-0.json), `manual.worker_inference`

**Settled by US-11.12.** The owner accepted it as built, including its failure behavior, in [Decision 0011](../decisions/0011-review-dispositions.md). Live runs through this worker are in [LIVE-GOAL-1](../evidence/LIVE-GOAL-1/summary.md), [US-10.1](../evidence/US-10.1/summary.md) and US-11.3's verification, each with its own results. Details of the first version below are history, and [the summary](../evidence/WORKER-INFERENCE-001/summary.md) has the current numbers.

## Plan

DH-W01.

- **Source:** no `SPECS.md` story owns this, and the requesting session asked for the user to confirm it belongs in scope. MP-01, MP-02, MP-06, MP-07 and MP-08 in [PRD-Model-Providers.md](../../PRD/PRD-Model-Providers.md). Live use stays with US-3.4.
- **Intended behavior and invariants:** `serve` can claim jobs through `process_next` with a real OpenRouter client from `adapters/models/factory.py`. Each job's route comes from its run's frozen `policy_snapshot`. The key resolves through `resolve_for_attempt` inside each attempt, and a missing key pauses the run. No paid call or real credential is used here.
- **Affected layers, contracts and states:** the worker entry point, the goal loop's claim path, the attempt's failure classes, catalog parsing and provider settings. No migration or public contract changes. Pause reasons `credentials_required`, `credential_unavailable`, `model_unavailable` and `network_before_acceptance` are new values of the existing stop reason.
- **Migration and operational impact:** none by default. `AUTOBOTS_WORKER_INFERENCE=enabled` turns it on, and that spends money once a key exists.
- **Verification and recovery plan:** unit tests through the real adapter and SDK over a fake transport, and `scripts/qualify_worker_inference.py` on a disposable stack. Turning it off means restarting the worker without the switch.

## Implementation

DH-W02. First committed in `965df5e`, and changed again by US-11.12.

- **Revision and changed paths:** `application/worker_inference.py` is new. Changed: `operations/worker.py`, `application/goal_loop.py`, `application/model_attempts.py`, `application/model_admission.py`, `application/provider_settings.py`, `adapters/loop_middleware.py`, `adapters/models/catalog.py`, all under `services/agent/src/autobots/`. Tests: `services/agent/tests/test_worker_inference.py`, `test_model_attempts.py`. Check: `scripts/qualify_worker_inference.py`, `tests/db/product_inference_worker.py`, `tests/db/product_inference_check.py`. Docs: [the operations runbook](../runbooks/operations.md) and `CODEBASE.md`.
- **Actual behavior:** off by default, in which case the worker still claims nothing. With the switch on, `InferenceSource.bind` replaces the model and route for each claimed job. A job with no usable key or catalog pauses with nothing reserved, after the cancel, obligation and route gates. Each attempt rechecks the catalog and price, reads the current key, records a stored key's version and builds one client. Reservations use the highest catalog rate that can apply, for 32,000 input and 512 output tokens.
- **Contract, migration and configuration changes:** one new setting, `AUTOBOTS_WORKER_INFERENCE`. `run_intent` now also answers `credential_unavailable` for a key that won't decrypt, and for an environment key whose last check couldn't reach OpenRouter. `classify_status` treats a status below 400, and 408, 504 and 524, as uncertain, and 404 as `model_unavailable`.
- **Stubs, deferred work and deviations from the plan:** beyond the brief, because the review found this path needed them: the failure classification, `Retry-After`, the per-call price and the slot wait during compaction. The upstream provider is still recorded as `unknown`, since the SDK doesn't expose it. Compaction needs matching `summarizer` and `executor` bindings. A price rise during a job stays under-reserved until its next claim, a recorded deviation from MP-07's "worst-known".

## Review

DH-W03.

- **Author and reviewer:** the implementing session; `autobots-reviewer`, in a separate read-only context, over two passes.
- **Reviewed fingerprint:** US-11.12's, in its [manifest](../evidence/US-11.12/gate-0.json). Its review read this path again, and its findings WI-1 to WI-7 are dispositioned in [its summary](../evidence/US-11.12/summary.md).
- **Findings and dispositions:** two blocking findings, both fixed: a billed reply recorded as never accepted, and `Retry-After` never read from a real SDK error. The second pass found nothing blocking. Non-blocking findings fixed: credential and configuration failures that escaped, the Astra over-reservation, `mark_invalid` ignoring which key got the 401, pricing edge cases, the uncapped `Retry-After`, the settings API failing on a damaged key, and the checks and docs that claimed too much. Left as they are: two narrow `mark_invalid` races that fail closed and clear with a revalidate, and the decision below.
- **Decided by the owner:** `rate_limited` and `provider_error` fail a run after their retries, and a person starts a linked new run ([Decision 0011](../decisions/0011-review-dispositions.md)). They fail today, `tests/db/goal_loop_check.py` asserts that for `provider_error`, and the earlier reviewer had recommended pausing on `rate_limited` at least.

## Verification

DH-W04. [Summary](../evidence/WORKER-INFERENCE-001/summary.md), bound by [US-11.12's manifest](../evidence/US-11.12/gate-0.json).

- **Classes and model transport:** mock (fake HTTP transport under the real SDK and adapter) and disposable. Nothing live.
- **Failures, errors, skips and limits:** in the summary. Not exercised through this worker: any live OpenRouter behavior, real response shapes or prices, two workers at once, a lost lease, and a persistent stack.

## Runbook

DH-W05.

- **Procedure:** [Turning on inference](../runbooks/operations.md#turning-on-inference).
- **Last exercised:** by `scripts/qualify_worker_inference.py` on a disposable stack. See the summary for its date and result.
- **Untested steps:** none here against a real key. The live runs named above used it under their own authorization.
