# Tasks

## 1. The box (Types and submits; Leaving the domains; Nothing to sign in or pay with; A bot check stops the call)

- [x] 1.1 The guard: `submits` mode for browser-use sessions (`GET`, `HEAD`, `POST`, `OPTIONS` on `https`), form submissions recorded as host and path, and the bot-check signals. Checked by pytest under `services/agent/tests` with fake CDP events
- [x] 1.2 The browser image's policy gains `AllowFileSelectionDialogs`, `PasswordManagerEnabled`, `AutofillCreditCardEnabled` and `AutofillAddressEnabled` off. Checked by the browser-use qualification's inspection of the box
- [x] 1.3 `browser_use_box.py`: `bot_check` ends the call before the next admission and outranks `refused_action`; submits reach the outcome. Checked by pytest under `services/agent/tests` with a fake admission and CDP log

## 2. Version 3 and the typed result (A typed result)

- [x] 2.1 `browse_goal` version 3: `output_schema` (at most 8 KB, a valid Draft 2020-12 schema, `x-link-fields` as dotted paths), and output `result`, public `submits` and `bot_check`. Versions 1 and 2 are unchanged and fail with the code `bot_check`. Move `EXPERT_TOOLS` and the schema fixture to version 3, update the guide, and make `jsonschema` 4.26.0 a direct dependency. Checked by pytest under `services/agent/tests` and `test_tool_schema_versions.py`
- [x] 2.2 The runner passes the schema as `StructuredDict` and prints the output. The worker strips the query outside link fields and validates, or stops `invalid_action`. Checked by pytest under `services/agent/tests`

## 3. Steps (What it saw is kept)

- [x] 3.1 Migration 66 `app_private.browse_steps`, private, with its header; `application/browse_steps.py` records and reads steps; `ToolContext.use_id` from the gateway. Checked by pytest and the db profile's disposable fixtures (`tests/db/checks/browse_steps_check.py`)
- [x] 3.2 The worker captures one screenshot per step into the run's private storage, with the step's page and submits. Checked by pytest with a fake CDP and store, and by the live check
- [x] 3.3 `GET .../tool-uses/{use_id}/steps` and the screenshot download, members only, with the Pydantic contract, OpenAPI and the generated TypeScript client. Checked by pytest, `contract_drift` and the db check
- [x] 3.4 The run's tool row shows a browse's steps with their screenshots, pages and submits. Checked by web unit tests and the run workspace browser suite under `apps/web/tests/browser`, with axe, on an arranged disposable run

## 4. Live

- [x] 4.1 The browser-use live check gains:
  - a form typed into and submitted by `GET` and `POST` on the qualification host, recorded as host and path only;
  - a submit leading outside, refused;
  - a synthetic CAPTCHA frame on the qualification host, ending the call `bot_check`;
  - a typed result, valid and invalid;
  - one screenshot kept per step;
  - the box's inspection: no key, password, cookie or card, downloads refused, no host file.

  Rebuild the images and run both qualifications. Checked by `scripts/qualify_browser_executor.py` on a disposable stack with a scripted model

## 5. Documents

- [x] 5.1 Amend PRD-Tool-Catalog "Autonomous browsing" for submits, `bot_check` and the output schema, and BX-03 for submits under YOLO. Update `README.md`, `README-DEV.md` and `CODEBASE.md`. Checked by reading them against Decision 0035 Y5, Y10 to Y12 and Y19
