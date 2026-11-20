# Design

## Context

Autobots' loop (Decision 0020) reads pages over CDP from the worker. Each browse gets a session: a hardened Chromium container on an internal network, and an egress sidecar that is its only way out (BX-01 to BX-04). US-17.2 added the worker's admitted model endpoint and the sidecar's relay to it on `proxy:9300`. browser-use 1.0.6 is a code-writing agent: its model calls a `python` tool whose cells run browser helpers over CDP, then `finish`.

Two probes against the current images, with a scripted model through a `ModelEndpoint`, showed:
- browser-use connects to the session's Chromium at `http://<browser IP>:9222`, since Chromium refuses a host name in the Host header. It calls the relay with plain, non-streamed requests and `tool_choice` auto.
- Its helpers refuse a host outside `allowed_domains` and a `file:` URL before any request, with the notices `blocked: <host> is not in allowed_domains (...)` and `is a file: URL or has no host`. A navigation the egress proxy refuses lands on `chrome-error://chromewebdata/` with `net::ERR_TUNNEL_CONNECTION_FAILED`.
- A 403 from the endpoint ends its run at once, with status `error`.
- Its container's environment held no worker value. It had no route to the metadata address, the internet or `host.docker.internal`, and reached only `proxy:3128`, `proxy:9300` and the browser.
- Model-written code started a download when nothing but CDP's download behaviour refused it.

## Goals / Non-Goals

**Goals:** the US-17.3 scenarios. browser-use runs in the box under YOLO, with the same contract, limits Y9, refusals ending the call, nothing reaching Browser Use's hosts, and its own qualification.

**Non-Goals:** submitting by `POST`, `bot_check`, typed results and step screenshots, which are US-17.4. The worker's request guard keeps refusing non-`GET` requests and bodies here, so browser-use may type and press but not submit a body yet. No real model or real YouTube in checks (Y18).

## Decisions

**D1. One Chromium per session, driven over CDP from a third container.** The browser-use container joins the session's internal network only, and drives the session's own Chromium: local, headless, a fresh profile in the browser's `tmpfs`. The egress rules, host resolver and caps that the loop's sessions qualified stay in force, and the worker keeps its own CDP connection to the same browser. *Alternative:* a Chromium inside the browser-use container. That would need the proxy flags and host rules again, and the worker couldn't watch it.

**D2. The worker's guard stays attached.** The worker attaches its request guard as for the loop, so schemes, methods and bodies stay refused (US-17.4 lifts methods and bodies under YOLO). The guard also logs top-frame navigations and downloads, which feed D4 and D5. CDP allows several clients, and each client's `Fetch` interception is its own.

**D3. Downloads off by Chromium's policy, and cancelled when forced.** Chrome for Testing reads `/etc/opt/chrome_for_testing/policies/managed/`, so the browser image installs `DownloadRestrictions: 3` there. It applies to the loop's sessions too, and with the guard's `deny` it refuses a download that a page or browser-use's own tools start. Model-written code can send any CDP command, and a probe showed `Browser.setDownloadBehavior allow` overrides the policy. So the guard also cancels any download that begins (`Browser.cancelDownload`), and that ends the call `refused_action`. A small file can complete before the cancel, into the box's own `tmpfs`, which holds nothing of the host and is removed with the session. Model code can already write files there itself (Y6).

**D4. The outcome and refusals are decided in the worker.** The box's printed report is untrusted data. It supplies the summary text (third-party data) and browser-use's status and steps. What ends a call is observed by the worker:
- **Refused actions.** Before admitting each request, the endpoint guard checks the worker's CDP log for a refused top-frame navigation or a download since the last request. It also checks the latest tool results for browser-use's own domain or `file:` refusal. If any is found, it refuses the request with 403 `refused_action` before admission, so no model step is taken, and the call ends `refused_action` with an empty summary. A page's own refused subresource isn't a top-frame navigation, so it is only counted in the proxy's log.
- **Admission refusals.** A refusal from admission (budget, model calls, time, a cancelled run) is recorded with its code, and the call fails with that code, as a `LoopStopped` does on the loop. A session the watcher removed because the attempt ended reports `cancelled`, as on the loop.
- **Status mapping.** Otherwise browser-use's status maps as follows: `completed` → `done`; `max_steps` → `max_steps`; `timeout` → `max_seconds`; `error` or a missing report → `browser_use_failed`.
- **Bounded spend.** The endpoint guard refuses past `max_steps` + 1 admitted calls (one delivery turn) with `max_steps`, so a box that ignored its limit can't spend more. The container is removed at `max_seconds` + the grace.

**D5. Visited URLs from the worker's CDP log.** The guard enables `Page` on each page session and records committed top-frame navigations. Visited is the `https` ones inside the call's domains, bare and de-duplicated in order, as the loop reports them.

**D6. browser-use's own qualification.**
- **Its own record.** browser-use is qualified apart from the executor: its image `autobots-browser-use:local`, a fingerprint of the executor's files plus its own (`services/browser-use/*`, its Dockerfile and ignore file, `browser_use_box.py`), its own label digest, and its own report `.checks/browser-executor/browser-use.json` with its required cases. `browser_use_qualified` needs the executor qualified as well.
- **Reversal.** Removing its image only turns browser-use off, which is Decision 0035's reversal. `make browser-images` builds all three images.

**D7. `browse_goal` version 2.**
- **Why a version.** A published schema never changes (Decision 0029 F13), so the wider limits are version 2 beside an unchanged version 1. Its `max_steps` (1 to 40) and `max_seconds` (10 to 600) are optional.
- **Resolution per engine.** browser-use resolves an unnamed limit to 25 steps or 300 seconds and caps at 40 and 600. The loop resolves it to its 10 steps or 120 seconds and caps at 20 and 300.
- **Approval.** An approval is asked only with YOLO off, so its shown limits are the loop's resolved ones.
- **Version 1 on browser-use.** A version 1 call under YOLO runs on browser-use with the limits it carries.
- **Versions in use.** `EXPERT_TOOLS` and the schema fixture move to version 2. `browse_goal` isn't in the recorded execution contract (`TOOL_VERSIONS`), so no compatible change is recorded for it.
- **Timeout.** The tool's gateway timeout rises to 600 + the grace + 30 seconds.

**D8. The runner.** `runner.py` reads its spec from `AUTOBOTS_BROWSE_SPEC`, builds `Agent(task, llm=ChatOpenAI("researcher", base_url="http://proxy:9300/v1", api_key="relayed"), browser=Browser(cdp_url=..., allowed_domains=...), use_vision=False, judge=False, highlight_actions=False)` and prints one JSON line. The model name and key are placeholders: the endpoint ignores the name, and the relay adds the real token. `ANONYMIZED_TELEMETRY=false`, `BH_TELEMETRY=0` and `BROWSER_USE_NO_UPDATE_CHECK=1` are set in the image. It runs as `pwuser` with `python -I`.

## Risks / Trade-offs

- **Model-written code has full CDP over the box's Chromium.** It can change any browser setting, including turning downloads back on past the managed policy. The proxy's host rules and the box's isolation hold regardless. The worker's guard cancels a forced download and ends the call, but a small one may land in the box's `tmpfs` first. Accepted by Decision 0035 Y6.
- **A page can steer the model within the domains.** Accepted by Decision 0035, "What this gives up".
- **browser-use's notices are text.** If a later version rewords them, the worker's CDP log still catches proxy refusals. The pin and the qualification bind the wording observed.
- **Approvals pending across the upgrade** were made for version 1 and keep it.

## Migration Plan

Rebuild with `make browser-images`, then run `python3.12 scripts/qualify_browser_executor.py`, which qualifies the executor and browser-use. Until browser-use passes, YOLO calls run on the loop. Rollback: remove the browser-use image or its report.

## Open Questions

None.
