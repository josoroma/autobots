# Verification — us-2-5-native-fastapi-next-js

Change: us-2-5-native-fastapi-next-js
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `b67b921`, working tree with this change, input fingerprint `59b46722e21e…`. Real local processes and Chromium. No database, service stack or model call. Detail: [the evidence summary](../../../docs/engineering/evidence/US-2.5/summary.md).

## Scenarios

**Start bounded native services: observed, with the "work" half static.** The runbook's commands, `uvicorn --factory autobots.api.main:create_configured_app` and `next start apps/web`, listen only on `127.0.0.1`, health returns 200 with the credential and 401 without it, the home page shows `available`, and nothing stays listening afterwards. A pytest fixture shows the pool is created and opened at startup, closed at shutdown, and untouched by building the app. A static test finds no background task or thread in `api/`. No run admission exists yet, so no real request has had long-running work to own.

**Guard the same-origin boundary: observed with an arranged identity.** Against real processes: a member gets 200 through the BFF. Another workspace's member gets 403. No session or a tampered one gets 401. A forged `Origin` or `Host` gets 403 before the API. A write without or with a mismatched CSRF token gets 403, and a valid one reaches the API. A client's own internal header is dropped. The API directly refuses a missing or forged internal credential and a forged host. Errors hold no token, stack or address, and page bodies and chunks hold no internal token. `pytest` also covers a wrong secret, wrong audience, expiry, `alg: none`, a missing expiry and a default store that denies everyone. 14 guard unit tests pass.

**Render Luma dark on a fresh visit: observed.** Under light and dark OS schemes, every sampled frame is dark, with no hydration error. Tokens resolve exactly as in the canonical file.

**Preserve an explicit appearance choice: observed.** Light survives navigation and reload, with light in every sampled frame. Dark persists under a light OS. Toggling issues no network request. No run state exists yet to mutate.

**Share accessible semantic styling: observed on the available screens.** Both pages in both modes have no axe WCAG 2.1 A or AA violation. Keyboard flow, focus outline, labels, the dialog on popover tokens, and status text and icon pass.

**Retain visual acceptance evidence: observed.** Screenshots and a summary bound to the fingerprint are under `docs/engineering/evidence/US-2.5/`. Concept images were not used.

`full` exit 0, 24 checks including `browser_qualification`, inputs stable. `fast` and `harness` exit 0.

## Findings

- **The suite found two real defects, both fixed.** `next-themes` applies any saved value as a class, so `garbage` rendered light tokens; a pre-paint script now drops invalid values. The default CSS build rewrote the tokens to `lab()`; modern `browserslist` targets keep `oklch()`.
- **Real Auth and membership are absent,** so the default store denies every workspace. Qualification arranges a membership and signs its own tokens. US-2.3 connects both, and only then is this boundary exercised end to end.
- **`dialog` text says workers run natively.** No worker exists yet; it describes the design, not current behavior.
- **`autobots.session` is read by the BFF, and nothing sets it yet.** The cookie's flags are US-2.3's.
- **The CSRF cookie uses `secure: false`,** since the MVP is loopback HTTP, per LM-04.
- **Dependencies added:** repo-local and pinned, listed in the proposal and toolchains runbook. Chromium, FFmpeg and headless shell take 572 MB in the ignored `.cache/ms-playwright`, installed once outside any check. `pnpm-lock.yaml` and `uv.lock` changed.
- **The `--retain` path writes into the repo,** so only that explicit form changes tracked files, and `full` does not use it.
- **`tests/toolchain/test_manifests.py`** now accepts `@autobots/*` workspace links. Its other offline tests still pass.
- **A classifier blocked one of my verification scripts** for a broad `pkill -f next-server`, which could have hit an unrelated server. I rewrote it to stop only the process groups it started.
- **Runbook:** `local-app.md`'s start and qualify commands were run, except the export and browser-install lines as written, and the recovery rows.
- This is not H1 or product acceptance.
