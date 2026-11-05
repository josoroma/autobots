# WORKER-INFERENCE-001 — Inference step in the product worker

Status: IN PROGRESS
Evidence: none recorded yet

## Plan

DH-W01.

- **Source:** no `SPECS.md` story owns this, and the requesting session asked for the user to confirm it belongs in scope. MP-01, MP-02, MP-06, MP-07 and MP-08 in [PRD-Model-Providers.md](../../../PRD-Model-Providers.md). Live use stays with US-3.4.
- **Intended behavior and invariants:** `serve` can claim jobs through `process_next` with a real OpenRouter client from `adapters/models/factory.py`. Each job's route comes from its run's frozen `policy_snapshot`. The key resolves through `resolve_for_attempt` inside each attempt, and a missing key pauses the run. No paid call or real credential is used here.
- **Affected layers, contracts and states:** the worker entry point, the goal loop's claim path, the attempt's failure classes, catalog parsing and provider settings. No migration or public contract changes. Pause reasons `credentials_required`, `credential_unavailable`, `model_unavailable` and `network_before_acceptance` are new values of the existing stop reason.
- **Migration and operational impact:** none by default. `AUTOBOTS_WORKER_INFERENCE=enabled` turns it on, and that spends money once a key exists.
- **Verification and recovery plan:** unit tests through the real adapter and SDK over a fake transport, and `scripts/qualify_worker_inference.py` on a disposable stack. Turning it off means restarting the worker without the switch.

## Implementation

DH-W02. Uncommitted on `delivery/epic-1`, because the request didn't ask for a commit.

- **Revision and changed paths:** `application/worker_inference.py` is new. Changed: `operations/worker.py`, `application/goal_loop.py`, `application/model_attempts.py`, `application/model_admission.py`, `application/provider_settings.py`, `adapters/loop_middleware.py`, `adapters/models/catalog.py`, all under `services/agent/src/autobots/`. Tests: `services/agent/tests/test_worker_inference.py`, `test_model_attempts.py`. Check: `scripts/qualify_worker_inference.py`, `tests/db/product_inference_worker.py`, `tests/db/product_inference_check.py`. Docs: [the operations runbook](../runbooks/operations.md) and `CODEBASE.md`.
- **Actual behavior:** off by default, in which case the worker still claims nothing. With the switch on, `InferenceSource.bind` replaces the model and route for each claimed job. A job with no usable key or catalog pauses with nothing reserved, after the cancel, obligation and route gates. Each attempt rechecks the catalog and price, reads the current key, records a stored key's version and builds one client. Reservations use the highest catalog rate that can apply, for 32,000 input and 512 output tokens.
- **Contract, migration and configuration changes:** one new setting, `AUTOBOTS_WORKER_INFERENCE`. `run_intent` now also answers `credential_unavailable` for a key that won't decrypt, and for an environment key whose last check couldn't reach OpenRouter. `classify_status` treats a status below 400, and 408, 504 and 524, as uncertain, and 404 as `model_unavailable`.
- **Stubs, deferred work and deviations from the plan:** beyond the brief, because the review found this path needed them: the failure classification, `Retry-After`, the per-call price and the slot wait during compaction. The upstream provider is still recorded as `unknown`, since the SDK doesn't expose it. Compaction needs matching `summarizer` and `executor` bindings. A price rise during a job stays under-reserved until its next claim, a recorded deviation from MP-07's "worst-known".

## Review

DH-W03.

- **Author and reviewer:** the implementing session; `autobots-reviewer`, in a separate read-only context, over two passes.
- **Reviewed fingerprint:** not bound yet. The final changes after the second pass are listed in [the summary](../evidence/WORKER-INFERENCE-001/summary.md) and weren't reviewed. Bind a fingerprint and review them on the tree after the blocker fixes merge.
- **Findings and dispositions:** two blocking findings, both fixed: a billed reply recorded as never accepted, and `Retry-After` never read from a real SDK error. The second pass found nothing blocking. Non-blocking findings fixed: credential and configuration failures that escaped, the Astra over-reservation, `mark_invalid` ignoring which key got the 401, pricing edge cases, the uncapped `Retry-After`, the settings API failing on a damaged key, and the checks and docs that claimed too much. Left as they are: two narrow `mark_invalid` races that fail closed and clear with a revalidate, and the decision below.
- **Open decision for the user:** whether `rate_limited` and `provider_error` should fail a run after their retries, or pause it. The sources don't decide. They fail today, `tests/db/goal_loop_check.py` asserts that for `provider_error`, and the reviewer recommends pausing on `rate_limited` at least.

## Verification

DH-W04. [Summary](../evidence/WORKER-INFERENCE-001/summary.md). No manifest yet, for the reason it gives.

- **Classes and model transport:** mock (fake HTTP transport under the real SDK and adapter) and disposable. Nothing live.
- **Failures, errors, skips and limits:** in the summary. Not exercised: any live OpenRouter behavior, real response shapes or prices, compaction, workflows or children through this worker, two workers at once, a lost lease, and a persistent stack.

## Runbook

DH-W05.

- **Procedure:** [Turning on inference](../runbooks/operations.md#turning-on-inference).
- **Last exercised:** by `scripts/qualify_worker_inference.py` on a disposable stack. See the summary for its date and result.
- **Untested steps:** the same command against a real key and live OpenRouter, which needs US-3.4's authorization.
