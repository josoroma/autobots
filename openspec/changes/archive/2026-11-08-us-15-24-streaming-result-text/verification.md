# Verification — us-15-24-streaming-result-text

Change: us-15-24-streaming-result-text
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 4/4 scenarios observed |
| Coherence    | Follows design.md |

## Commands

- **`python3.12 scripts/verify.py --profile fast`:** exit 0. Pytest ran 816 tests, including 5 in `test_result_stream.py`, and mypy passed.
- **`python3.12 scripts/verify.py --profile db`:** exit 0 at 2026-11-08T19:18Z, including every case below.
- **`python3.12 scripts/verify.py --profile full`:** exit 0, with 41 browser tests passed.
- **`python3.12 scripts/qualify_worker_inference.py`** (in no profile; disposable stack, fake transport): exit 0, with all 56 cases passing in 99 s.
  - It ran the product worker entry point, the real SDK and streamed requests.
  - Its cases include reasoning continuation (LC-23), the cut-off reply, the dropped connection, malformed replies, 429 retries and settlement.
  - The request shape now includes `stream_options`.

**Fixes made along the way:**
- **Cut-off tool call.** The first qualifier run under streaming showed that assembly repairs a cut-off tool call into a valid call with truncated arguments. Arguments are now parsed strictly, which also needed LangChain's factories so each call keeps its `type`. Two worker steps failed until that `type` was added.
- **US-15.18 bind check.** An API under uvicorn was killed (exit 137) on its first `local-status` read, because the check duplicated every descriptor, guarded ones included. It now looks at socket descriptors only and never duplicates or closes one. A manual run then answered three reads with `loopback_only: true`.
- **Leftover stack.** A qualifier run interrupted mid-way left disposable stack `dd6ba7bc`. It was removed through the guarded `remove_stack` path.

## Scenario: Result deltas, ephemeral and coalesced — PASS (disposable stack, scripted streaming model; browser)

`tests/db/result_stream_check.py` drove a run through the goal loop with `StreamScript`, listening on `autobots_result_text`:
- **Run:** it succeeded.
- **Text:** the report's deltas, segment 2 after the working note's segment 1, joined to exactly the 2,592-character content.
- **Stored artifact:** `run_files` holds the same text, and the published artifact's sha256 matches it.
- **Coalesced:** 4 notifications came from 424 streamed fragments, each carrying only `run_id`, `segment`, `offset` and `text`.
- **Nothing durable:** 0 `result.text.delta` rows in `run_events`.
- **Typed frame:** the API frame builder made a typed `result.text.delta` `RunEvent` at schema_version 1, and dropped another run's payload.

In the browser (`stream-result.spec.ts`, first test), the `ops-n` owner watched a run written by `result_stream_live.py`:
- the "Being written." note and live text appeared;
- axe found no violations;
- the live text was a strict prefix of the final content;
- the helper reported `succeeded` and 0 durable deltas;
- the shown result then equalled the stored content exactly, and the live text was gone.

## Scenario: Reconnect rebuilds from the artifact — PASS (browser, disposable stack)

The browser went offline for 2.5 s while the result was being written, then back online. Once the run finished, the result shown equalled the stored content exactly.

## Scenario: Nothing private is streamed — PASS (disposable stack; unit)

The scripted model streamed reasoning (`PRIVATE-REASONING-MARKER`), a raw framework value (`RAW-FRAMEWORK-VALUE-MARKER`) and other tools' arguments. None of these appeared in any delta:
- either marker;
- the paths;
- `propose_plan`, `publish_artifact` or `complete_task` arguments;
- the task title;
- anything tool-shaped.

`test_result_stream.py` checks the same thing offline, and also that a file outside `outputs/` never streams.

## Scenario: The preference turns live text off — PASS (browser, disposable stack)

With "Stream text as it's written" off (Settings showed it unchecked), the live text never appeared while the result was written, sampled every 200 ms. The stored result then appeared, equal to the content. The identity suite's presentation-only test also toggles the new preference, with no request and no state change.

## Findings

- **Interpretation (design.md):** "result text" is the `content` of a `save_artifact` call to `outputs/`. It is the one tool argument streamed, because it is the result being written. Every file under `outputs/` streams as its own segment.
- **Not established:** streamed calls against a live OpenRouter route. Decision 0022's streaming decision says that needs its own capped authorization. Also not established: H1 and product acceptance.
- **Left alone:** a disposable stack, `cb16aed9`, from before this run (up 25 hours), and a local API on port 8001 started yesterday.
