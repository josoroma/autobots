## Why

US-15.24 implements [PRD-Studio ST-01 and SE-03](../../../PRD-Studio.md#streaming), under [Decision 0022 D4 and its streaming decision](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#streaming-decision), Decision 0017 Q13 and SP-011. A run's result appears only once its artifact is stored. The owner decided that every worker model call streams, so its text can show while it's written.

## What Changes

- **Every admitted model call streams.** `AdmittedModel` reads the reply as a stream and assembles it, so the ledger settles from the same usage and cost a whole reply reports.
  - **Tool-call arguments** are parsed strictly, as an unstreamed reply's are, so a call cut off mid-argument stays an invalid tool call.
  - **A stream that fails after its first chunk** is `partial_stream`, so it is reconciled rather than retried.
  - **Production:** `AttemptModel` gains `astream`.
- **A `ResultTap` per run, set by the goal loop.** As `save_artifact` calls stream, it reads only the `content` of a file whose path is under `outputs/`. It coalesces that text, about every 150 ms, and sends it with Postgres NOTIFY on `autobots_result_text`, which stores nothing. It never reads reasoning, a framework value, the path or any other argument. A failure to send never stops the run.
- **The live stream** opens a `LISTEN` connection of its own and passes this run's deltas on as `event: live` frames. Each frame is a typed `RunEvent` with the new `result.text.delta` payload at `schema_version` 1. It carries no SSE `id`, so it never moves the replay cursor. Durable events never include it.
- **The run view** shows the live text under Result. It replaces that text with the stored artifact once `artifact.published` arrives, which also covers a reconnect. It skips live frames when "Stream text as it's written" is off. That preference is new in Appearance, on by default, and applied before paint like the other preferences.
- **Fake transports** answer streamed requests: a shared `completion_to_sse` helper serves the unit-test fake and the worker inference qualifier's upstream. The qualifier now expects the `stream_options` request field.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `run-workspace`: streamed result text.

## Impact

- **Python:** `adapters/loop_middleware.py`, the new `adapters/result_stream.py`, `application/worker_inference.py`, `application/goal_loop.py`, `api/event_routes.py`, `contracts/runs.py`, and the new `operations/fake_stream.py`.
- **Contract:** the generated contract and client.
- **Web:** `run-workspace.tsx`, `appearance-control.tsx` and `app/layout.tsx`.
- **Tests:**
  - new `test_result_stream.py`, plus `test_worker_inference.py`;
  - `tests/db/product_inference_worker.py` and `scripts/qualify_worker_inference.py`;
  - new `tests/db/stream_script.py`, `result_stream_check.py` and `result_stream_live.py`, registered in `qualify_identity.py`;
  - new `stream-result.spec.ts`, plus `slice-visual.spec.ts`.
- **Also fixed: the bind check from US-15.18.** It duplicated every descriptor, and macOS kills a process that duplicates a guarded one, so an API under uvicorn died on its first Operations read. It now looks at sockets only, and never duplicates or closes them.
