# Verification — us-2-1-pinned-local-supabase-service

Change: us-2-1-pinned-local-supabase-service
OpenSpec verify: VERIFIED by the main session, with the limits below. No independent review, per Decision 0003.
Verified: 2026-11-05

Base revision `4f41904`, working tree with this change. Real Docker on a disposable project. No persistent stack, cloud or model call.

## Scenarios

**Publish only approved local services: observed on a disposable project.** `scripts/verify.py --profile db` exit 0, with `supabase_stack.py qualify` passing 18 of 18 cases on `autobots-disposable-cf79fcee` in about 22 seconds:
- 8 services, digest-pinned and ARM64, all running and healthy. Realtime, Edge Functions and Supavisor removed.
- `lsof` shows each published port only on `127.0.0.1`, and a non-loopback address is refused. `docker compose ps` shows exactly `api-gw 127.0.0.1:…->8000/tcp` and `db 127.0.0.1:…->5432/tcp`.
- Through the published port with the pinned `psycopg`: the same cluster identifier as inside the `db` container, server port 5432.
- Studio: no publication, 401 anonymously, 401 with a wrong password, 307 with the operator password, through the gateway.
- Auth health 200 through the gateway, `disable_signup` true, REST 401 with no key.
- Rendered with `OPENAI_API_KEY` and `OPENROUTER_API_KEY` offered from the host: Studio's key stays empty, also at runtime, and no OpenRouter setting reaches any service. Telemetry off.
- Afterwards no project containers or volumes remain, and 32 other Docker resources are the same.

**Protect unrelated services: observed, naturally occurring.** `preflight` with the proposed ports: exit 1, `54321` and `54322` reported as held by another stack on `*:`, "nothing was stopped". That stack is unrelated, and it was not contacted or stopped. Fixtures: a held and a wildcard port are conflicts and the holder still accepts; free ports exit 0. Fourteen rendering faults are refused, including a retained wildcard.

## Findings

- **The proposed ports are not available on this machine right now.** `54321` and `54322` belong to another project's stack, so the real stack cannot use them until you stop that or choose others. A decision for whoever starts a persistent stack.
- **No persistent start exists.** This story qualifies the boundary on disposable ports.
- **A 307 was accepted as Studio answering.** It is a redirect, and the destination page was not rendered.
- **Storage was checked for health only** in this story. US-1.7's negative cases ran on an older image; US-2.3 and US-2.4 own authorization on this stack.
- **Studio's assistant** is disabled through the empty key, as the PRD says. No UI was opened to confirm it.
- **Images were pulled once**, about 6.9 GB in total, to resolve digests. Checks do not pull. Digests are registry index values read from this machine.
- **`tests/toolchain/test_scaffold_scope.py`** now allows `infra/supabase/`.
- **US-1.8's review approval is voided by these source changes**, as it stated it would be. `evidence.py validate US-1.8` now fails on its fingerprints by design; its record describes the baseline at that commit.
- **Runbook:** `local-supabase.md`'s commands were run, except the recovery rows and the upgrade path, which are untested.
- This is not H1 or product acceptance.
