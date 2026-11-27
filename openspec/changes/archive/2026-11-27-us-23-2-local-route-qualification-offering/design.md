# Design: local route qualification and offering (US-23.2)

## Context

- **The runner today.** `operations/route_qualification.qualify` runs `route_fixtures.QualificationRun`: twelve fixtures, three trials, each call through `self.build()`. Before running it reads OpenRouter's catalog, refuses without `--paid`, and holds every call in a `paid/ledger.Ledger` under an authorized cap.
- **Stored qualifications.** `agent_runtime.route_qualifications` holds one row per profile, with `status` either `qualified_with_limits` or `not_qualified`, and is recorded by migration. Settings lists them through `provider_settings.read_route_qualifications`, which includes local profiles as not qualified (US-23.1).
- **OpenRouter offering** is the fixed `OFFERED_FOR_NEW_RUNS` in `domain/models.py`, which leaves local profiles out.

## Decisions

### D1. The same suite, a local branch

`qualify_local(profile, out, port, client=None)`:
- checks the served model with `check_served` first, refusing with nothing sent if the wrong model answers or nothing does;
- builds each call with `local_chat_model`, and a test passes a `LoopbackClient` on a fake transport;
- runs the same `QualificationRun` with a ledger capped at 0 and a worst case of 0, so every call is still written down, and each settles at the reported cost of 0;
- gives each call `LOCAL_CALL_SECONDS` = 1,800, a new `call_seconds` field on `QualificationRun` whose default is OpenRouter's 90 seconds.

The CLI's `--profile local_…` runs on request with no `--paid`. That flag gates spend, and a local route has none.

### D2. Offering gate

The five capabilities named by Decision 0041 A7 are `plain_text`, `tool_auto`, `tool_required`, `schema_flat` and `stream_text`. The report:
- sets `offerable` only when each passed in all three trials;
- lists every other fixture that failed or was unsupported in `limits`;
- sets `recorded_status` to `qualified_with_limits` or `not_qualified`.

`limits_text` turns that list into the sentence a migration stores. So what the code decides and what is stored can't disagree.

### D3. Measurements

`operations/local_route_measurements.measure(port, context)` streams three chat completions straight to the server with synthetic prompts of about 8K, 32K and 62K tokens. Each prompt extends the last, as the by-hand probe's did, so the prompt cache serves the earlier part. For each it records:
- the time to the first content;
- reading speed, as the new prompt tokens over that time;
- writing speed, as the output tokens over the rest;
- the prompt tokens from the reply's usage.

It also records the server's peak footprint, sampled every 2 seconds by `/usr/bin/footprint` on the PID `lsof` finds listening on the port, or `None` with a reason where either tool is missing. These measure the route, not the gateway, so they don't go through admission.

### D4. Offering on the Local source

`application/local_offering.local_offers(qualifications)` returns one `LocalOffer` per local profile: offered or not, with its date, configuration and limits, or a reason.
- **Offered:** a stored row for the profile's own canonical ID with `qualified_with_limits`.
- **No row, or a row for another canonical ID:** "its local route hasn't passed US-3.4's suite: no qualification is stored".
- **`not_qualified`:** "its local route's qualification didn't pass: <limits>".

`OFFERED_FOR_NEW_RUNS`, OpenRouter's offering, is unchanged, so new work on OpenRouter naming a local profile is still refused. US-23.3 reads `local_offers` when the source is Local.

### D5. Recording Bonsai 2.5's result

Migration `20261127000069_bonsai_local_route_qualification.sql` inserts Bonsai 2.5's row with the live report's status, date, configuration and limits, citing US-23.2. Its text comes from the report, including the pins and llama.cpp's build. `SHIPPED_MIGRATIONS` becomes 69. The owner applies it to the persistent install, never a check.

## Risks / Trade-offs

- **The live run takes a long time.** About 39 calls at 4 to 11 tokens a second of writing, plus about 17 minutes of measuring.
- **Memory.** The Studio and Docker run beside the server. The report records swap before and after.
- **Thinking.** A fixture that fails because thinking used up 16 output tokens isn't a gating one: truncation passes on `finish_reason == "length"` either way.
