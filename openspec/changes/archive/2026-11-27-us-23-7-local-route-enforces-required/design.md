# Design: a local route enforces required tool calls (US-23.7)

## Context

- **US-23.1's request.** `LoopbackClient.body` sent a named tool as `tool_choice` `required` with only that tool, and passed `required` through. Enforcement was llama.cpp's.
- **What US-23.2 observed.** Against llama.cpp 1.1.0, Bonsai 2.5 answered `tool_required` in text until its 512 tokens ran out (0 of 3), and `tool_named_conflict` held 2 of 3. So the route was recorded `not_qualified` (migration 69).
- **What the server takes, probed by hand on 2026-11-27.**
  - `/apply-template` with `tools` and `tool_choice` `none` still renders the tools in the prompt.
  - A chat completion with `tools`, `tool_choice` `none` and a `response_format` JSON schema is accepted, and the reply's content is JSON matching the schema.
  - "Say hello" under a schema admitting only Weather returned a Weather call. With Weather and ClockTime both admitted, a time question returned ClockTime. With only Weather admitted under a prompt preferring ClockTime, it returned Weather, twice in two tries.

## Decisions

### D1. Keep the tools described, and let the schema choose

For a `required` choice (or LangChain's `any`) or a named tool, the body keeps every tool, sets `tool_choice` `none` so the server neither forces nor parses a call, drops `parallel_tool_calls`, and adds:

```json
{"type": "json_schema", "json_schema": {"name": "tool_call", "strict": true, "schema": ...}}
```

The schema is one object per allowed tool, combined with `anyOf` when there are several: `{"name": {"enum": [<tool>]}, "arguments": <its parameters>}`, both required, nothing else allowed. A tool's own `$defs` move to the root under a per-tool prefix, with its `$ref`s rewritten, so two tools can't collide. A named tool the request doesn't offer is refused before anything is sent.

Keeping every tool in the prompt, rather than only the named one, means the history's earlier calls still render against their tools. The constraint, not the prompt, decides the name, which is what MP-A07's counterexample tests.

### D2. Ask for the reply whole

A constrained call is sent with no `stream`. Only a complete reply can be checked against the schema, and a streamed prefix is never an executable call (MP-02, MP-08). For a caller that streamed, the checked reply is handed back as two chunks: the message with its tool call, then its usage. So `ChatOpenRouter`'s stream assembly and the ledger's settlement are unchanged.

### D3. Check, then convert

- `finish_reason` `length`: the message becomes empty text with no call, so `model_replies.finished` reads it as incomplete and the loop's cut-off handling applies, as on any route.
- Otherwise the content must parse as JSON with exactly `name` and `arguments`, the name must be allowed, and the arguments must validate against that tool's parameters with `jsonschema`. The result is one `tool_calls` entry with a new `call_…` ID, empty content and `finish_reason` `tool_calls`.
- Anything else raises `ProviderFailure(OTHER)` with the reason `required_tool_call_not_returned`. `OTHER` isn't retried by `call_with_policy`, and the loop closes it as a refused call, not an uncertain one. No new stop code is added, because A18 names none.

### D4. Decision 0005's guard

`test_no_application_code_asks_for_strict_output` allows `adapters/models/local_server.py`, citing A18, and still fails on any other application file. Decision 0041's "Requirements revised" records why: OpenRouter routes still ask for no strict output, and the local route's flat structured output passed qualification.

### D5. Requalify, and store the result over migration 69's row

- **Running it.** On the owner's request: `llama-server --version` and the weights' SHA-256 against the pin and `DOWNLOAD-MANIFEST.json`. Then the runbook command, and `route_qualification --profile local_bonsai_2_5_27b --no-measure`. US-23.2's report and ledger are moved to `.checks/route-qualification/us-23-2/` first, since a new run writes over the report and adds to the ledger.
- **No new measurements.** The server, weights and flags are unchanged, and A18 changes only how required calls are sent. So US-23.2's speed and memory figures still describe the route, and the stored configuration cites them.
- **Storing it.** Migration 70 updates the row for the profile's own canonical ID, as migration 50 did for Sol, with evidence `US-23.2, US-23.7`. If it qualifies, its limits carry SQLI-12's sentence, and `scripts/app_db.py`'s check of that names Bonsai 2.5.

## Risks

- **Grammar coverage.** llama.cpp's schema-to-grammar may not enforce every JSON Schema keyword. The `jsonschema` check catches what the grammar lets through, and fails the call.
- **Reasoning models.** Inkling 2 Mini's reasoning can't be turned off. How a constraint interacts with its reasoning is untested here, and Inkling isn't requalified.
