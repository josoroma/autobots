---
paths:
  - "infra/**/*"
  - "**/Dockerfile*"
  - "**/*compose*.yml"
  - "**/*compose*.yaml"
  - "scripts/operations/**/*"
---

# Mac-local operations

The [local deployment PRD](../../PRD-Local-Mac-Deployment.md) owns topology. Use `autobots-docker-local` for configuration/recovery changes.

- Native Next.js/Python; local Docker Supabase/tools. Publish loopback only. Supabase gateway hosts authenticated Studio; expose no raw Studio port.
- Native direct DB traffic uses host `54322` to `db:5432`, not pooler routing. Check merged ports so upstream wildcard bindings do not survive.
- Pin/qualify images on Apple Silicon, inspect health/resource limits and persistent mounts. Never print secret-expanded Compose configuration.
- Studio AI stays disabled with empty `OPENAI_API_KEY`; no OpenRouter credentials in Studio or tool containers. No hosted tracing or implicit telemetry.
- Distinct disposable projects/ports/volumes and ownership guards precede cleanup. Persistent startup, migration, restore/reset/prune are not ordinary verification or hook actions.

## Check and review

Check: the `operations` profile of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
