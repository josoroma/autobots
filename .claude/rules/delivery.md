# Source authority and delivery

Read `.claude/autobots.json` and the mapped contract before a bounded work item. Current user scope and approved owning PRDs define intent; CODEBASE is descriptive. Preserve `SP-*`, `EPIC-*`, `US-*` IDs and source coverage. Missing decisions remain questions; conflicts remain visible.

Follow [DH-W01–06](../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract): proportional plan, actual implementation record, independent read-only review, current verification and exercised runbook. Templates, skipped checks and mocks are not live evidence. The coordinator owns status changes.

Keep writer scopes disjoint. Never repair implementation in a supposedly independent review. Fingerprint final relevant tracked/untracked source, nonsecret configuration, locks, generated contracts and verifier; changed inputs invalidate affected evidence.

Version reviewed redacted summaries/manifests under `docs/engineering/evidence/<work-item-id>/`; ignored `.checks` raw artifacts have explicit retention/availability. Do not save secrets or user content as proof. No automatic model calls, installs, service startup or persistent data changes in hooks.

When delivering through `/ohmyorch:deliver`, follow [the OhMyOrch delivery rule](ohmyorch-delivery.md) instead of this DH-W procedure, by the user's decision. Everything else here applies to work outside that loop.

`harness`, `fast`, `full`, `db` and `operations` verification are implemented. `db` and `operations` use disposable targets only; passing any profile cannot establish H1 or product acceptance. Honor current scope: harness adaptation alone does not authorize product construction.
