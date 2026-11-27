# Tasks: US-23.2, local route qualification and offering, at no spend

## 1. The runner's local branch

- [x] 1.1 Give `QualificationRun` a `call_seconds` field, defaulting to OpenRouter's 90. Add `qualify_local` and the CLI's local profiles to `operations/route_qualification.py`, with no `--paid`, cap, key or catalog, `check_served` first, `local_chat_model` for each call and 1,800 seconds a call. OpenRouter routes are unchanged. Checked by pytest: a fake server answers every fixture in three trials, a catalog stub fails the test if read, and a wrong model or a stopped server refuses with nothing sent.
- [x] 1.2 Add the report's local fields: `fake_server` or `live_local` evidence, the served model ID, the pins, US$0.00, `offerable`, `limits`, `recorded_status`, `limits_text` and what it doesn't establish. Checked by pytest, including a fake server whose required tool call fails in one trial, which records that failure, lists `tool_required` in its limits and isn't offerable.

## 2. Measurements

- [x] 2.1 Add `operations/local_route_measurements.py`: three streamed requests of about 8K, 32K and 62K prompt tokens, each recording the time to the first content, reading and writing speed and prompt tokens, plus the server's peak footprint. Checked by pytest on a fake streaming server, and by reading the live report.

## 3. Offering

- [x] 3.1 Add `application/local_offering.local_offers`: offered only with a stored `qualified_with_limits` row for the profile's own canonical ID, with its date, configuration and limits, and otherwise a reason naming what hasn't passed. Checked by pytest, with Bonsai 2.5 offered and Inkling 2 Mini not.
- [x] 3.2 Test that on OpenRouter, a new run, the workspace default, a role override and an Expert binding naming an offered local profile are still refused `model_not_offered`. Checked by pytest.

## 4. The live qualification

- [x] 4.1 Start `llama-server` serving Bonsai 2.5's pinned Q2_0 by the runbook command, after `llama-server --version` and a SHA-256 check of the weights. Run the suite's three trials and the measurements. Keep the raw report in `.checks/route-qualification/`, then stop the server. Checked by the live report.
- [x] 4.2 Record the result by migration `20261127000069_bonsai_local_route_qualification.sql`, from the report's status, date, configuration and limits, and set `SHIPPED_MIGRATIONS` to 69. Checked by the harness migration-header test and the db profile.

## 5. Docs and checks

- [x] 5.1 Amend option-b-contract SP-008's qualification paragraph for local routes. Add the runbook's local Qualify command and update `CODEBASE.md`. Checked by reading each against Decision 0041 A7.
- [x] 5.2 The fast, db and harness profiles pass. Checked by `scripts/verify.py`.
