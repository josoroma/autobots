# Verification — us-12-7-record-why-call-outcome-unknown

Change: us-12-7-record-why-call-outcome-unknown
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Name the exception behind an uncertain call | PASS | Through the worker on a fake HTTP transport, `qualify_worker_inference.py`: an unparseable 200 logs `status: 200`, `ResponseValidationError` and its cause `pydantic_core…ValidationError`. A dropped reply logs `httpx.RemoteProtocolError` with no status. `verification_check.py`, through the real loop with a scripted model: a 504 and a `RuntimeError` with a `ValueError` cause |
| Say which path had no exception | PASS | `verification_check.py`, through the real loop on a disposable database: `reason: call_time_limit` on a hung call and `reason: run_interrupted` on a cancel, one event each. Not run through the worker, as its 120-second limit has no setting |
| Cover a partial stream that is arranged | PASS (arranged) | `verification_check.py`: a handler raises `partial_stream` with output, as nothing in the code raises it. One event, `failure: partial_stream`, and its output isn't in the log |
| Keep a secret out of the log | PASS | `verification_check.py`: a sentinel in the message and cause isn't in the 5 events read. `test_worker_inference.py` shows the exception really carries the text, and that the formatted line doesn't. Redaction doesn't recognize either value |
| Observe it through the product's worker | PASS | `qualify_worker_inference.py`, 53 cases, disposable stack, `worker.main` over a fake HTTP transport, no paid call. One event per run, with identifiers cut to 8 characters. The arranged reply text and every key are absent from all process logs. The run pauses with its reservation held. The time limit, an interrupted run and a partial stream weren't run through the worker |
| Change nothing else | PASS | No file changed under `supabase/` or `apps/`, by `git status`. `ProviderFailure` gains an optional `reason`, read only by the log. Classification and pausing tests pass unchanged. The pause stays a stated limit, by Decision 0014 |
| Say where to look | PASS | `operations.md`, in the `uncertain_acceptance` row: the event, what it names, and that it doesn't say what was charged, so a person still looks in OpenRouter's records |

Checks: `fast` exit 0, `db` exit 0, with identity at 445 cases and `app_db` at 449, and `qualify_worker_inference.py` exit 0.

## Findings

- **The log, not a column.** A column needs a migration, which would leave the stopped install behind the code. So the inspector doesn't show the cause. Recorded in Decision 0014.
- **The earlier wrapper covered less than this does.** `logging_worker.py` saw only exceptions with no status, so round 1's cause could have been on a path rounds 2 to 5 wouldn't have shown. This covers all of them.
- **`charge_not_reported`, `cancelled_after_dispatch` and a call left by a cut drain don't take these paths,** so they get no event. The runbook's text is in the `uncertain_acceptance` row only.
- **Other uncertain statuses:** a 408 or 524 goes down the same path as the 504 case, and wasn't run separately.

## Not exercised

Nothing live. This doesn't explain US-12.4's round 1, which it can't reach, and the event hasn't yet caught a real pause.
