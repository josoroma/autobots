# Proposal

## Why

US-17.2 in SPECS.md: [Decision 0035](../../../docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md#decision) Y7 and Y16, and Decision 0020 L3. browser-use (US-17.3) runs in the isolated box and calls a model through an OpenAI-compatible client. Every such call must be an admitted call of the run, on its frozen `researcher` route, with the same reservation, ticket, receipt, budget and `model_calls` as the browsing loop's steps. The box must never hold a key, and nothing but that browse's box may reach the endpoint.

## What Changes

- **The endpoint.** A per-browse model endpoint the worker serves, `adapters/model_endpoint.py`:
  - It listens on `127.0.0.1` on a free port.
  - It answers `POST /v1/chat/completions`, as JSON or, when asked to stream, as a short server-sent stream.
  - It requires a per-session bearer token.
- **Admission.** Each request goes through the loop's admission, `application/model_endpoint.py`. The OpenAI messages and tools become LangChain messages and tool definitions, and are sent by `middleware.admitted(...)` on the run's frozen `researcher` route, through the shared transport. The reply is translated back. The model the request names is ignored, and the endpoint has no model client of its own.
- **Typed refusals.** A refusal answers with a typed code before anything is sent:
  - past the run's budget, model calls or time, or for a cancelled run: the admission's own stop code;
  - for content the route isn't qualified for, such as an image: `content_not_qualified`;
  - without the session's token: 401 `token_required`.
- **The relay.** The browse's egress sidecar gains a model relay on port 9300 of the session's internal network. It forwards to the worker's endpoint, adding the token, so the box reaches the endpoint only through it and never holds the token.
  - `BrowserExecutor.start` takes the endpoint's port and token.
  - The sidecar reaches the worker through `host.docker.internal`, mapped to the host gateway.
- **Requalification.** The executor qualification gains cases for the relay, and the images are rebuilt and requalified.
- **Documents.** PRD-Tool-Catalog BM-01 to BM-04, the operations runbook's browser executor section, and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `browser-model-endpoint`: the admitted OpenAI-compatible endpoint for the browser box, its refusals, and who can reach it.

### Modified Capabilities
- None as requirements. `browser-executor` gains the relay, which the qualification records.

## Impact

- **Python:** new `adapters/model_endpoint.py` and `application/model_endpoint.py`, plus changes to `adapters/egress_proxy.py` (the relay) and `adapters/browser_executor.py` (the start argument and the host mapping).
- **Checks:** a new disposable-database check, `tests/db/checks/model_endpoint_check.py`, plus `scripts/qualify_browser_executor.py`'s relay cases and unit tests.
- **Images:** the egress image changes, so `make browser-images` and the executor qualification run again.
- **No consumer yet:** US-17.3 wires the endpoint to browser-use. Nothing calls it in production until then.
