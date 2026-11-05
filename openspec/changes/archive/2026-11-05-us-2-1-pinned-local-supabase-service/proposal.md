## Why

The application needs a project-scoped local Supabase stack on this Mac, and LM-03/LM-04 require a pinned release, loopback-only publications and protection for unrelated services. Upstream's defaults publish wildcard ports and a pooler, and fix global container names.

## What Changes

- Vendor the pinned `self-hosted/v0.8.3` release, unmodified, in `infra/supabase/upstream/`, with hashes.
- `infra/supabase/compose.overlay.yaml`: digest-pinned images with `pull_policy: never`, loopback-only gateway and direct database ports replacing upstream's lists, project-scoped names, named volumes, empty Studio `OPENAI_API_KEY`, telemetry off, and Realtime, Edge Functions and Supavisor removed.
- `scripts/supabase_stack.py`: `preflight` reports a port conflict and stops nothing, and `qualify` checks the merged configuration and actual listeners on a disposable project. The `db` profile runs it.
- The eight pinned images were pulled once, explicitly, to resolve digests. The check itself never pulls.

**Limits:** no persistent stack start. The story qualifies the boundary, and ports `54321` and `54322` are held by another project here, so qualification uses disposable ports. Later stories decide when a persistent stack starts.

## Capabilities

### New Capabilities

- `local-supabase-boundary`: pinned release, loopback publications, authenticated Studio and a non-destructive port preflight.

### Modified Capabilities

None.

## Impact

New `infra/supabase/`, `scripts/supabase_stack.py`, `tests/harness/test_supabase_stack.py` and `docs/engineering/runbooks/local-supabase.md`. Updates `scripts/verify.py`, `scripts/harness_lib.py`, `tests/toolchain/test_scaffold_scope.py`, the harness runbook and `CODEBASE.md`. Local Docker images added; no database, cloud or model call.
