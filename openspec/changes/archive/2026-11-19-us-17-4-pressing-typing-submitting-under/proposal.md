# Proposal

## Why

US-17.4 in SPECS.md: [Decision 0035](../../../docs/engineering/decisions/0035-browser-use-typing-and-transcripts.md#decision) Y5, Y10, Y11, Y12, Y16 and Y19. Under YOLO, browser-use runs in the box (US-17.3) but the worker's request guard still refuses every request with a body, so it can type and press but not submit. A search form or a "Show transcript" button needs presses and submits on the allowed domains. With no approval under YOLO, a person needs a record afterwards of what it saw and where it submitted. A bot check must end the call rather than be fought. A call should be able to ask for a typed result.

## What Changes

- **Submits under YOLO.** For a browser-use session, the worker's guard lets `GET`, `HEAD`, `POST` and `OPTIONS` through on `https`, bodies included. Every other method and scheme stays refused, and the loop's sessions stay read-only. The guard records each form submission as its host and path, never its values or query.
- **`bot_check`.** The guard recognises a bot check from the page itself:
  - a CAPTCHA frame (reCAPTCHA's checkbox or challenge, hCaptcha, Cloudflare's challenge platform, DataDome, Arkose);
  - a Google "sorry" address.

  The next model request is then refused before admission, and the call stops `bot_check`. Nothing solves, hides or retries. No stealth setting, user agent change or Browser Use Cloud is used.
- **Nothing to sign in or pay with.** The browser image's Chromium policy also turns off file selection dialogs, the password manager, and card and address autofill. The qualification shows the box holds no key, password, cookie or card, refuses downloads, and that its file system holds no host file.
- **`browse_goal` version 3.** Its input adds an optional `output_schema`: a JSON Schema object of at most 8 KB, whose top-level `x-link-fields` names its link fields (Y19). Its output adds:
  - `result`, the typed result: validated against the schema, with the query kept only in the declared link fields;
  - `submits`, each submit's host and path, public;
  - `bot_check` among the stop reasons.

  A result that doesn't validate stops the call `invalid_action`. Versions 1 and 2 stay registered, unchanged. On browser-use they fail with `bot_check` as a code, and their submits are kept only in the step record.
- **Step screenshots.** At each browser-use step, the worker captures one screenshot of the box's page over its own CDP connection and keeps it in the run's private storage. Beside it, a private row holds the step's page (host and path) and its submits. Members read them through `GET /v1/runs/{run_id}/tool-uses/{use_id}/steps` and an authorized screenshot download. The run's tool row shows them. Nothing sends a screenshot to a model (Y16).
- **Documents.** PRD-Tool-Catalog "Autonomous browsing" (AB-01, AB-03, `bot_check`, the output schema) and BX-03 (submits under YOLO), the guide, `README.md`, `README-DEV.md` and `CODEBASE.md`.

## Capabilities

### New Capabilities
- `browser-use-typing`: pressing, typing and submitting under YOLO, `bot_check`, typed results and step screenshots for browse_goal on browser-use.

### Modified Capabilities
- None as requirements. `browser-use-engine` keeps its requirements, and the guard and box gain the behaviour above.

## Impact

- **Database:** migration 66 adds `app_private.browse_steps`.
- **Python:** `browser_cdp.py` (submits, bot checks), `browser_use_box.py` (steps, screenshots, result), `browsing_tool.py` and `contracts/browsing.py` (version 3), `tool_definitions.py` and `tool_gateway.py` (the use id), a new `application/browse_steps.py`, a new `api/browse_step_routes.py`, and `contracts/browse_steps.py`. `jsonschema` 4.26.0, already in the worker's lock, becomes a direct dependency.
- **Images:** the browser image's policy and the runner change, so both qualifications run again.
- **Web:** the tool row's steps, and the generated client.
- **No paid call, and no real CAPTCHA or YouTube in checks** (Y18). Submits and bot checks are arranged on the qualification host.
