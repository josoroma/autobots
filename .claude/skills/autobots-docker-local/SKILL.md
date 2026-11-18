---
name: autobots-docker-local
description: Author or inspect Autobots local Docker/Supabase configuration and operational checks, preserving Mac-native app services, loopback networking, private volumes and target-safe recovery.
---

# Local infrastructure

Relevant paths: `infra/**/*`, `**/Dockerfile*`, `**/*compose*.yml`, `**/*compose*.yaml` and `scripts/operations/**/*`.

Read `.claude/autobots.json`, the mapped deployment/contract and [DH-08](../../../docs/PRD/PRD-Development-Harness.md#dh-08-docker-and-local-operations-standards). Use the pinned self-hosted Compose source; do not replace it with a hosted project or treat the CLI test stack as the persistent stack.

- Next.js and Python stay native on this Mac; Docker hosts Supabase and scoped tools. Qualify reviewed image versions/digests on Apple Silicon.
- Bind published ports to `127.0.0.1`. Gateway `54321` includes authenticated Studio; direct database `54322` maps to `db:5432`, not Supavisor. Do not expose raw Studio or leave inherited wildcard bindings through a Compose merge.
- Validate rendered configuration without printing expanded secrets. Separate liveness from dependency readiness; inspect persistent mounts, resource limits and dependency/schema readiness.
- Disable Studio AI and leave its `OPENAI_API_KEY` empty; never pass OpenRouter keys to Studio or tool containers. Disable unsolicited application telemetry. Images/workspaces must not contain secrets or a Docker socket.
- Disposable tests use unique projects/ports/volumes and ownership markers. Backup qualification restores database, Storage bytes and separately protected key material into an isolated target and checks records/hashes.

Ordinary checks and hooks do not start Docker/services, reset databases, prune or remove volumes. Explicit authorized operations must use implemented target guards and the declared runbook; routine stop/start preserves data. No additional confirmation is needed for already authorized operations.

Return topology/config changes and actual validation/recovery evidence. A rendered configuration is not a running deployment, and a passing `operations` profile is disposable evidence, not proof about a persistent stack.

Failure behavior: templates, skipped tests and missing tools never count as passing evidence. Report a failed or unavailable check as such; ordinary checks still do no persistent reset or volume removal.
