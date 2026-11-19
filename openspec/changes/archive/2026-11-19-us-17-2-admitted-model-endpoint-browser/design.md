# Design

## Context

See proposal.md for why.
- **How a browsing step is admitted.** `browsing_loop.admitted_steps` sends one call through `middleware.admitted(StepRequest, handler, route)`. The handler invokes the attempt model, wrapped in `AdmittedModel` so it answers only inside an admitted dispatch. `LoopStopped(code)` carries any stop.
- **How browser-use calls a model.** browser-use 1.0.6's `ChatOpenAI(model, base_url=...)` uses Pydantic AI's OpenAI chat model:
  - It sends `POST {base_url}/chat/completions` with function tools and `tool_choice`, and no strict schemas.
  - It always streams (`agent/loop.py`, `request_stream`).
- **How the box is wired.** Its containers sit on an internal Docker network, and only the egress sidecar also has a way out. The worker runs natively on the Mac, so it can't join that network.

## Goals / Non-Goals

**Goals:** the endpoint, its admission and refusals, and the token and relay that keep everything but the browse's box out.

**Non-Goals:**
- Running browser-use (US-17.3).
- Any change to the browsing loop.
- Image input, which no route is qualified for (Y16).

## Decisions

1. **One endpoint per browse, opened and closed with the call.** It is a minimal `asyncio` HTTP/1.1 server on `127.0.0.1:0`, one request per connection, with a 2 MiB body cap. It needs no web framework: the sidecar already serves raw HTTP the same way. The worker holds the middleware, model and route it was opened with, rather than reading a context variable from the server's tasks.

2. **Translation by LangChain's own converters.**
   - `convert_to_messages` turns OpenAI messages into LangChain messages, tool calls and tool results included.
   - Tools pass through `bind_tools` as OpenAI function definitions.
   - `tool_choice` maps `required` to `any`; `auto` and `none` pass through; a named function stays named.
   - The reply's `AIMessage` becomes an OpenAI `chat.completion`, with its tool calls and the usage the ledger recorded.

3. **Streaming answers after admission.** The call is admitted and completed first. A streamed request then gets a short stream:
   1. one chunk with the role, content and tool calls;
   2. one chunk with `finish_reason`;
   3. one usage chunk when `stream_options.include_usage` asks;
   4. `[DONE]`.

   This is a valid stream for Pydantic AI's parser, and admission stays one call either way.

4. **Refusals are typed JSON errors,** `{"error": {"code", "message"}}`:
   - 400 for malformed input, an unknown path or method, or `content_not_qualified`, before admission;
   - 401 `token_required`;
   - 403 with `LoopStopped`'s code (such as `budget_exhausted`, `model_calls_limit`, `run_time_limit` or `cancelled`), raised by admission before anything is sent;
   - 413 for an oversized body.

   Pydantic AI surfaces any of these as an HTTP error, and browser-use stops (US-17.3 maps it).

5. **The token and the relay.** The token is 32 random bytes, compared in constant time. Only the sidecar's relay holds it. It listens on 9300 on the browse's networks and forwards only `POST /v1/chat/completions` to `host.docker.internal:<port>`, replacing any `Authorization` header with the token.
   - The sidecar maps `host.docker.internal` to the host gateway, so it works on Linux too.
   - The browser container is on the internal network only, so it reaches the endpoint only through the relay.
   - A process on the Mac without the token is refused.
   - The relay forwards to one fixed port and one path, so it opens nothing else of the host to the box (BX-02).

6. **Qualification.** `scripts/qualify_browser_executor.py` gains three cases, run with a stub step that answers a fixed reply (no model):
   - the browser container reaches the endpoint through `proxy:9300`, and the endpoint sees the token;
   - a direct request to the host port from the browser container fails;
   - a request without the token is refused.

   Admission itself is proven on a real database by `model_endpoint_check.py`.

## Risks / Trade-offs

- **Docker Desktop's `host.docker.internal`** forwards to services bound to the host's loopback. Qualification proves it on this Mac, and a host where it doesn't fails qualification rather than browsing.
- **Streaming is buffered.** A browse sees no partial tokens, which only costs latency inside the box.
