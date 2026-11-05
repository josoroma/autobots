# Verification — us-2-3-local-identity-workspace-grants

Change: us-2-3-local-identity-workspace-grants
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `91770af`, working tree with this change, input fingerprint `ccc2426b288f…`. Real Auth, PostgREST, Storage, Postgres, Envoy, the API and a browser, on a disposable pinned stack. No persistent target, cloud or model call. `--profile db` exit 0 under `env -i`; `scripts/qualify_identity.py` passed 36 of 36 cases in about 26 seconds. `full`, `fast` and `harness` also exit 0.

## Scenarios

**Use local password ownership: observed.**
- `DISABLE_SIGNUP=true`: `/auth/v1/signup` returns 422.
- `bootstrap_owner` creates two owners through `/auth/v1/admin/users`, with workspaces and memberships, by a real subprocess. A real password sign-in returns 200 for each, and a wrong password 400.
- In Chromium through the real form: signed in, "1 workspace". The cookie is `HttpOnly` and `Strict`, not readable by script, and no token is in `localStorage`. `/api/v1/session` returns the workspace from the real database through the runtime role. The other workspace returns 403. A wrong password shows a safe message and leaves no session, and signing out returns 401. No page body held the service key or password. Sign-in without CSRF returns 403.
- No external identity provider is configured or contacted.

**Reject cross-boundary access: observed, with Realtime by absence.**
- PostgREST through the gateway: a member reads its run. Another workspace reads none. Anonymous and a forged token get 401. Lease columns and writes get 403.
- `Accept-Profile: app_private` and `agent_runtime` get 406. A real table in each is 404 from `public`, and neither appears in the service-role API description.
- Storage on real `storage-api` with real Auth tokens: a member uploads, reads and lists. Another workspace, anonymous and a forged token cannot read. Another workspace cannot upload, list or delete. An unscoped path and uploading into another workspace are refused. There is no public read.
- **Realtime:** the service is removed from this stack by the overlay, and `pg_publication_tables` shows 0 tables from either private schema. No running Realtime service was tested.

## Findings

- **Storage refusals are 400s,** the service's own mapping. The checks require 4xx and no bytes, and positive controls exist for each path.
- **Storage's policy file runs as superuser,** outside the migration history, because Storage owns those tables. It is idempotent, and has no history row or checksum. A persistent setup must run it deliberately.
- **`bootstrap_owner` is not idempotent.** A repeat with the same email exits 1. If the Auth call succeeds and the database insert fails, the user exists with no workspace; recovery is not implemented and not exercised.
- **Python verifies HS256 with the shared Auth JWT secret,** matching this release's legacy mode. Asymmetric signing keys are not configured or tested.
- **The session is read with `getSession()`** and the API verifies the token, so the BFF never trusts its contents. Token refresh is left to `@supabase/ssr` and was not exercised with an expired session.
- **Service-role use is limited to bootstrap and this check.** SP-005's note that a service credential bypasses Storage RLS applies once artifact code exists; none does.
- **Identity qualification adds about 30 seconds to `--profile db`,** which now creates three disposable stacks.
- **Runbook:** `local-app.md`'s bootstrap path was run through the qualification with disposable values, not as a copy of its command line. The persistent steps are written for a stack that does not exist yet, and are untested.
- This is not H1 or product acceptance.
