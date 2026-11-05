# Verification — us-4-6-sanitized-event-replay-run

Change: us-4-6-sanitized-event-replay-run
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `c4ae9e3`, working tree with this change. The real API, web app, Storage and Postgres on a disposable stack, in Chromium, with a scripted model behind one fixture run. `scripts/qualify_identity.py` exit 0, 98 cases, including 6 new browser tests. `--profile full` passed.

## Scenarios

**Reconnect from committed events: observed.**
- Events arrive live: a pause through the API moves the page to `paused` and adds sequence 2.
- For the disconnect, the stream ended and the test blocked reconnection, so the page showed `reconnecting` with its last known state. Two more commands ran meanwhile, and sequence 4 stayed absent. Unblocking gave `live`, sequences exactly `1, 2, 3, 4` with no duplicate, and the right status. A reload rebuilt the same four.
- Retained history arranged by deleting sequences 1 and 2: replay reports `gap`, the page says earlier activity is no longer retained, shows sequence 3 and takes its status from the snapshot.
- Closing a viewer leaves the run queued at version 1. A later cancel reaches another viewer as `cancelled`, and its stream ends with `ended`.
- Another workspace gets a clear refusal on the page and 404 from replay, stream and snapshot. A signed-out stream gets 401.

**Keep private execution state private: observed with arranged content.**
- A raw `model.reasoning` event arranged in `run_events` is absent from replay and the page. A unit test rejects unknown types, extra fields and non-objects.
- An evidence summary arranged with a key-like string shows `[redacted]`, in the snapshot and on the page.
- The page and snapshot hold no `checkpoint`, `object_path`, `policy_snapshot` or lease fields. The projection reads typed records, and never checkpoints.
- Paused, failed, reconnecting and unavailable each show distinct text with data attributes. axe reports no WCAG A or AA violation in dark or light. A keyboard reaches the skip link first.

## Findings

- **Fixed during this story:** a quiet run's stream sent no bytes, so its headers never arrived and the page stayed at `loading`. The stream now sends a comment first. `context.setOffline` also doesn't drop an open EventSource, so the test blocks reconnects instead, with a short stream lifetime set through `AUTOBOTS_STREAM_SECONDS`.
- **The real connection loss wasn't a network failure.** The stream ended normally and reconnects were blocked in the browser. A cut TCP connection takes the same `onerror` path, which wasn't exercised separately.
- **Timing targets aren't measured.** SP-021's "visible under one second" isn't benchmarked, and the stream polls every 0.5 seconds.
- **Redaction is pattern-based.** It catches key shapes and bearer tokens, not arbitrary sensitive text a model might write. Text is rendered as text, so it can't inject markup.
- **Not built:** a list of runs, chat, the role map and approvals on this screen, and a `stop_reason` event in the timeline. Those belong to later stories, or come from the snapshot here. Reading the stream's first event for authorization happens before its first byte, so a refused stream is a plain status.
