# Proposal: a local route enforces required tool calls, and Bonsai 2.5's route is qualified again (US-23.7)

## Why

US-23.2 recorded Bonsai 2.5's route as not qualified: llama.cpp 1.1.0 didn't enforce a required tool call for its template, so the model answered in text, and a named tool held against a contrary prompt only twice in three trials. On 2026-11-27 the owner answered "Decide it", which recorded Decision 0041 A18: a local route enforces a required or named tool call itself, and Bonsai 2.5's route is qualified again. No local profile can be offered, and Local can't be chosen, until a route passes.

## What Changes

- **The loopback client enforces a required or named tool call (A18).**
  - The tools stay in the request, so the chat template still describes them, with `tool_choice` `none`.
  - A `response_format` JSON schema admits one call: the name of a tool the request offers, or the named one only, and arguments matching that tool's parameters.
  - The reply is asked for whole, checked against the tool's parameters and turned into that one tool call.
  - A reply cut off by its output cap reads as cut off, with no call. One that otherwise doesn't parse or match fails the call as `other`, with nothing passed on as text and no retry.
  - A call that leaves the choice to the model, and structured output, are sent as before.
  - **BREAKING** for US-23.1's request shape only: a named tool is no longer sent as `required` with only that tool.
- **Decision 0005's guard** allows this one request outside the qualification runner. OpenRouter routes still ask for no strict output.
- **Bonsai 2.5 requalified live** on the owner's request: US-3.4's suite in three trials against the owner's `llama-server`, at US$0.00. A new forward migration records the result over migration 69's row. If the five gating capabilities pass, the row is `qualified_with_limits`, and the Local source offers the profile.
- **Docs:** MP-02's local routes paragraph, the local app runbook's Qualify step, and `CODEBASE.md`.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `local-model-route`: a required or named tool call is enforced by the route, replacing "One named tool is sent as required".
- `local-route-qualification`: the suite qualifies the route as it now sends tool calls, Bonsai 2.5's route is qualified again, and its stored result decides offering.

## Impact

- **Python:** `adapters/models/local_server.py`, `application/schema_release.py`, and the tests for the local route, its qualification and Decision 0005's guard.
- **SQL:** one forward migration that updates Bonsai 2.5's `agent_runtime.route_qualifications` row. No schema change. Migration 69 keeps its bytes.
- **Database checks:** `scripts/app_db.py`'s SQLI-12 check gains Bonsai 2.5, and a db check reads the stored row and the Local source's offering from it.
- **Docs:** PRD-Model-Providers MP-02, `docs/engineering/runbooks/local-app.md` and `CODEBASE.md`. Decision 0041 already records A18 and its effect on Decision 0005.
- **The owner's machine:** `llama-server` serving Bonsai 2.5's Q2_0 on 127.0.0.1:9931 while the live run lasts, then stopped.
