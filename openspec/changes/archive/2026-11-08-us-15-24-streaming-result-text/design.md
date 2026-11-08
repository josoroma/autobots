## Decisions

- **Every call streams.** The owner chose this for US-15.24 (Decision 0022's streaming decision), because which call writes the result isn't known in advance.
  - **Assembly:** the assembled reply carries the same usage, cost and finish reason, so admission and settlement are unchanged.
  - **Strict arguments:** assembly would repair partial JSON, so each call's arguments are parsed strictly, keeping a cut-off call invalid as before.
  - **Mid-stream failure:** is `partial_stream`, the existing uncertain class.
  - **Delegates without `astream`**, such as test doubles, are still called whole.
- **What "result text" means:** the `content` argument of a `save_artifact` call whose path is under `outputs/`, the run's deliverable files. It streams only once the path is known, each file as its own segment. ST-01 forbids streaming tool arguments; this content is the one exception, because it is the result being written.
- **The channel is Postgres NOTIFY**, which stores nothing, with payloads under 8 KB in pieces of up to 1,500 characters. The tap has its own connection, separate from the loop's. Each live stream has its own `LISTEN` connection, which also serves as the stream's wait between polls.
- **The frame** is a `RunEvent` whose `sequence` names the durable event it follows. It is sent as `event: live` with no SSE `id`, so replay never sees it.
- **The client** treats the stored artifact as the result. It joins live pieces by offset, and a piece that doesn't continue the text marks the view as joined partway.
- **Not established:** streamed calls against a live route. That needs its own capped authorization.
