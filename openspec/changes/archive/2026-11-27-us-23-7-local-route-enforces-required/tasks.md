# Tasks: US-23.7, a local route enforces required tool calls, and Bonsai 2.5's route is qualified again

## 1. The loopback client (A18)

- [x] 1.1 In `adapters/models/local_server.py`, send a `required` or named tool call with every tool described, `tool_choice` `none` and a `response_format` JSON schema for one call of an allowed tool with its parameters (`required_tools`, `tool_call_schema`). Refuse a named tool the request doesn't offer before sending. Send `auto`, no choice and structured output as before. Update the module's docstring and replace US-23.1's named-tool test. Checked by pytest in `tests/test_local_required_tool_calls.py`: the bodies sent, Weather and LookupCode under `required`, and MP-A07's two-tool counterexample against a server that answers ClockTime whenever the schema admits it.
- [x] 1.2 Check the reply and turn it into one tool call. A reply cut off by its cap keeps no text and no call. One that doesn't parse, names a tool not offered or other than the named one, or has arguments off its schema fails as `ProviderFailure(OTHER)`, with one chat completion and nothing passed on. Checked by pytest with fake servers that count the chat completions they receive, directly and through the loop middleware.
- [x] 1.3 Ask a streamed constrained call for its reply whole, and hand it back as a tool-call chunk and a usage chunk. A cut-off streamed reply reads as cut off. Checked by pytest.
- [x] 1.4 Show that a run's required and named calls go to the loopback only, reserving US$0, with a fake OpenRouter client that fails if built and a catalog that fails if read. Checked by pytest through the loop middleware.
- [x] 1.5 Let Decision 0005's guard allow `local_server.py` only, citing A18. Checked by `tests/test_route_qualification.py`.

## 2. The suite and the live requalification

- [x] 2.1 Make the fake suite server answer a constrained request within its schema, and show that `tool_required` and `tool_named_conflict` pass through the constraint in three trials. Checked by pytest in `tests/test_local_route_qualification.py`.
- [x] 2.2 On the owner's request, check `llama-server --version` and the weights' SHA-256 against the pin and the manifest. Start the server by the runbook command, run the suite's three trials with `--no-measure`, keep the raw report in `.checks/route-qualification/`, and stop the server. Checked by the live report: `live_local`, US$0.00, and each gating fixture's verdicts.
- [x] 2.3 Record the result by migration `20261127000070_bonsai_local_route_requalified.sql`, which updates Bonsai 2.5's row for its own canonical ID, with its header lines and SQLI-12's sentence if it qualifies, and set `SHIPPED_MIGRATIONS` to 70. Add Bonsai 2.5 to `scripts/app_db.py`'s SQLI-12 check. Add `tests/db/checks/local_offering_check.py`, which reads the stored row and the Local source's offering from it. Checked by the harness migration-header test, `tests/test_schema_release.py` and the db profile.

## 3. Docs and checks

- [x] 3.1 Amend MP-02's local routes paragraph (A18), the local app runbook's Qualify step and `CODEBASE.md`. Checked by reading each against A18 and the code.
- [x] 3.2 The fast, db and harness profiles pass. Checked by `scripts/verify.py`.

## 4. From verify

- [x] 4.1 Show that no chunk of a streamed constrained call carries the reply as text: every chunk's content is empty. Checked by pytest in `tests/test_local_required_tool_calls.py`.
- [x] 4.2 Show that the suite's constrained calls reach only the loopback, with no key, alongside its `fake_server` evidence and nothing reserved. Checked by pytest in `tests/test_local_route_qualification.py`.
