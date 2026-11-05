## Why

Local ownership must be real before any product data exists, and SP-005 and LM-05 require local password Auth with public signup disabled, verification at both the BFF and Python boundaries, and private schemas and Storage closed to everyone else.

## What Changes

- `autobots.operations.bootstrap_owner`: creates the owner through the Auth admin API, plus a workspace and membership. Secrets come only from the environment.
- `PostgresMembership` through the restricted runtime role, and `GET /v1/session`, which reports the verified identity and memberships.
- Next.js sign-in and sign-out through `@supabase/ssr`, which the PRD names, on the server only, with an HttpOnly same-site cookie.
- `supabase/bootstrap/storage.sql`: a private bucket, and policies constrained by workspace membership.
- `scripts/qualify_identity.py`: real Auth, the API, the BFF in a browser, PostgREST and Storage with nonprivileged identities, on a disposable pinned stack, in `--profile db`.

**Limits:** no persistent stack is started. Realtime is removed from this stack, so "absent from Realtime" is shown through publications and configuration, not a running service. Invitations and other owner controls belong to later stories.

## Capabilities

### New Capabilities

- `local-identity`: local password ownership, verified membership and closed private boundaries.

### Modified Capabilities

None.

## Impact

`apps/web`, `services/agent/src/autobots/api`, `operations/`, contracts, `supabase/bootstrap/`, `scripts/verify.py`, `scripts/harness_lib.py`, `scripts/qualify_web.py`, the lock files and runbooks. Adds pinned `@supabase/ssr` and `@supabase/supabase-js`. Disposable Docker only. No model call.
