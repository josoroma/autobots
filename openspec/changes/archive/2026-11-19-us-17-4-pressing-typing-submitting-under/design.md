# Design

## Context

US-17.3 runs browser-use in the box under YOLO. The worker keeps its own CDP connection with its request guard, judges the outcome from what it observes, and admits each model request through the browse's endpoint. The guard still refuses every request with a body. browse_goal has versions 1 and 2, whose published schemas are pinned (Decision 0029 F13). Tool uses are recorded in `app_private.tool_uses`, and the run workspace lists them from `GET /v1/runs/{id}/tool-uses`. Artifacts sit in the run's private storage behind an authorized download.

## Goals / Non-Goals

**Goals:** the six US-17.4 scenarios, each checked against the qualification host only (Y18).

**Non-Goals:** the Transcript reader (US-17.5), and any solving of or hiding from bot checks.

## Decisions

**F1. Submits only on browser-use sessions.** The guard takes `submits`, set only for a browser-use session, which runs only under YOLO (Y15). Then `GET`, `HEAD`, `POST` and `OPTIONS` (a `POST`'s CORS preflight) go through on `https`, bodies included. Every other method and scheme stays refused. Loop sessions are unchanged.

**F2. A submit is a form submission.** The guard records `Page.frameRequestedNavigation` with reason `formSubmissionGet` or `formSubmissionPost` on its page sessions, as host and path. The query, fragment and values are never read into the record. A page's background `POST` isn't a submit.

**F3. Bot checks from the page itself (Y10, Y16).**
- **Signals.** The guard checks every request URL it pauses and every committed top-frame URL against a fixed list:
  - reCAPTCHA's visible checkbox (`/recaptcha/(api2|enterprise)/anchor` without `size=invisible`) or its challenge (`.../bframe`);
  - an hCaptcha frame document;
  - Cloudflare's challenge platform (`/cdn-cgi/challenge-platform/`, `challenges.cloudflare.com` documents);
  - DataDome's `captcha-delivery.com`, an Arkose frame;
  - a Google `/sorry/` page.
- **What it records.** A match records the host. It refuses the next model request with `bot_check` before admission, and the call stops `bot_check`, which outranks `refused_action`.
- **Why these signals.** An invisible reCAPTCHA script on an ordinary page isn't a bot check. The check uses only the URL, never a model.

**F4. Version 3.** Version 3 adds two things, while versions 1 and 2 keep their pinned schemas:
- **Input.** `output_schema` (Y19), a JSON object of at most 8 KB that `jsonschema` accepts as a Draft 2020-12 schema. Its optional top-level `x-link-fields` lists dotted paths whose `[]` steps into arrays, such as `flights[].url`.
- **Output.** `result`, `submits` (public), and `bot_check` among the stop reasons.

A version 1 or 2 call that meets a bot check fails with the code `bot_check`. `EXPERT_TOOLS` and the schema fixture move to version 3, and new grants take it.

**F5. The typed result.**
- **In the box.** The runner passes the schema to browser-use as `pydantic_ai.StructuredDict` and prints `result.output`.
- **In the worker.** The output is untrusted data. Every string that parses as an `http(s)` URL outside a declared link field loses its query and fragment. The result is then validated against the schema. A failure stops the call `invalid_action` with no result.
- **Visited URLs** stay bare, as before.

**F6. One screenshot per step, taken by the worker.**
- **Capture.** At each model request, before admission, the worker captures the most recently navigated page over its own CDP connection (`Page.captureScreenshot`, JPEG quality 60). Each step is pictured once, as it began, with the submits made since the previous one. A refused request is pictured too, showing where the browse stopped, such as a CAPTCHA or an error page. Nothing is captured after the box's run, because browser-use closes its tabs when it stops (observed in the live check).
- **Storage.** The object goes to `{workspace_id}/{run_id}/browse-{use_id}-{step}.jpg` in the run's private storage. The store allows one name below the run. A row in `app_private.browse_steps` holds the tool use, step, object path, size, digest, the page's host and path, and that step's submits.
- **Without an object store,** or when a capture or upload fails, the row is kept without a picture and the browse goes on.
- **Model access.** No screenshot reaches a model.
- **The use id.** `ToolContext` gains `use_id`, which the gateway passes to a read like browse_goal, so the steps belong to their tool row.

**F7. Reading the steps.**
- **List.** `GET /v1/runs/{run_id}/tool-uses/{use_id}/steps` (`listBrowseSteps`) lists them for a member of the run's workspace.
- **Screenshot.** `GET /v1/runs/{run_id}/tool-uses/{use_id}/steps/{step}/screenshot` serves the JPEG inline, `nosniff`, `no-store`, outside the generated client, through the BFF's existing proxy.
- **The table.** It is private: granted to the runtime role only, with no PostgREST or Realtime access.
- **The web.** The tool row of a browse_goal use with steps shows a disclosure listing each step's page, submits and screenshot, with alt text.

**F8. Nothing to sign in or pay with.** The browser image's policy adds:
- `AllowFileSelectionDialogs` false;
- `PasswordManagerEnabled` false;
- `AutofillCreditCardEnabled` false;
- `AutofillAddressEnabled` false.

The qualification inspects the box: no mount, no worker value, an empty profile with no cookie, a file system holding no host file, and downloads refused. The box's image files are public image content, not host files. Chrome 156 marks the two autofill policies deprecated and still applies them, which `chrome://policy` shows.

## Risks / Trade-offs

- **What it types within the domains is up to the task.** Accepted by Decision 0035, "What this gives up".
- **The bot-check list is fixed.** An unlisted check is only met as page content, and the call goes on to its limit. Each new kind is a change to the list.
- **A form submitted by script without a navigation** (a background `fetch`) isn't recorded as a submit.

## Migration Plan

Migration 66 creates the table. Rebuild the images and run both qualifications again.

## Open Questions

None.
