---
paths:
  - "services/agent/src/autobots/adapters/models/**/*"
  - "services/agent/src/autobots/application/**/*"
  - "services/agent/src/autobots/adapters/loop_middleware.py"
  - "apps/web/app/api/settings/**/*"
---

# OpenRouter application inference

The [provider PRD](../../docs/PRD/PRD-Model-Providers.md) owns IDs, credentials, routing and budgets. Read `autobots-model-gateway` for changes here.

- Three approved OpenRouter profiles, by Decision 0019; all roles initially Terra, except that `researcher` defaults to Sol once Sol is offered. DeepSeek isn't offered for new runs until qualified, by Decision 0013, nor Sol until its route is qualified. Decision 0041 adds local profiles, answered by the owner's `llama-server` on 127.0.0.1 through the same factory, each checked against the served model ID before every call, at US$0, and offered only once its route qualifies. No alternate provider, hidden model default or fallback between sources.
- Freeze canonical/wire identities and role policy at admission; changed routes create linked new runs. Late-resolve credential references per attempt without serializing secrets/clients.
- Honor configured key precedence; nonblank invalid higher-priority keys block fallback. Missing credentials block inference, not local UI/files/settings. Save & validate is metadata-only and cannot auto-run a draft.
- Enforce fresh catalog mapping, supported parameters, required routing flags, budget reservations and concurrency. A correct response does not prove an ignored tool constraint was enforced.
- Fake transports are the default test path even with a real key present. Live qualification is an explicit bounded task; developer assistant model configuration is separate and unchanged.

## Check and review

Check: the `full` profile of [`scripts/verify.py`](../../scripts/verify.py). Review: [`autobots-review-change`](../skills/autobots-review-change/SKILL.md).
