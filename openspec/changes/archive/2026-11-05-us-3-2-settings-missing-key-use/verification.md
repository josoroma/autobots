# Verification — us-3-2-settings-missing-key-use

Change: us-3-2-settings-missing-key-use
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `80b2b28`, working tree with this change. Real local Auth, Postgres, API, BFF and Chromium on a disposable pinned stack. **OpenRouter is a local fake**, with placeholder keys. No real credential or real provider call. `--profile db` and `full` under `env -i` exit 0.

## Scenarios

**Keep non-AI work available: observed.** Signed in with no key: home, settings and models pages load. Pressing Run returns `credentials_required`, with the draft still in the box. Exactly one `POST /runs/intent` occurs, and only from that click. No file surface exists yet to read, so "reads files" isn't exercised. A later story brings artifacts.

**Validate without launching a run: observed against the fake upstream.** `Save & validate`: authentication says the key authenticated, the field is empty afterwards, the source says encrypted, the catalog is reported separately, and live qualification says not qualified. No response body or browser storage holds the key. A stored row holds no plaintext. **Return to your draft** restores the text and sends no run request until Run is pressed. The fake's log holds only `GET /api/v1/key` and `GET /api/v1/models`, across the whole suite. A catalog outage leaves a valid save committed, with the catalog shown unavailable and every model unavailable.

**Preserve valid configuration: observed.** A rejected key says the previous key is unchanged, and its version stays. A simulated outage says "could not be checked" and commits nothing. A stale `expected_version` on PUT and DELETE returns 409 `stale_version`, without the submitted key, and nothing changes. A member gets 403 `owner_required`, on credentials and policy. A workspace outside the session's memberships gets 403. An environment-managed key shows no field, and PUT gets 409 `environment_managed`. Disconnect blocks model work again, and a new key works afterwards. Model policy is versioned, a stale write gets 409, and an unapproved profile gets 422.

## Findings

- **The real key endpoints have not been called.** The fake encodes this project's reading of `GET /key` and `GET /models`. US-3.4 owns live qualification, which also proves the 401 and 403 behavior.
- **`ready` starts nothing,** and says so in the UI. Run admission is a later story. The gate exists so every model path has one place to check.
- **Catalog status is fetched on each status call,** which is real network use once a real upstream is connected, with no caching. MP-02's five-minute rule needs a cache before paid dispatch.
- **`validating` is a UI state only.** The form disables while in flight, and the server relies on version checks to refuse a duplicate commit. Concurrent duplicates weren't raced.
- **`ModelPolicyUpdate` isn't strict,** since FastAPI validates parsed JSON and strict mode refuses strings for enums. Unknown fields and values are still refused. Other request bodies with enums or UUIDs need the same care, and real-HTTP tests are what catch this.
- **Stored model policy isn't consulted yet.** The route stores it and returns the effective map. Run admission must read it.
- **Draft text in `sessionStorage`:** DS-02 forbids storing credentials and sensitive run state in the browser. A goal draft is user-typed text, kept for this tab only. Whether that's acceptable for sensitive goals is a judgment the sources don't explicitly make, and I judged it covered by "preserve the draft". Say if you'd rather keep it server-side.
- **Request and response logs:** the BFF logs nothing, and `uvicorn` access logs were off in this run. Access logs hold paths and not bodies, but production log settings aren't configured yet.
- This is not H1 or product acceptance.
