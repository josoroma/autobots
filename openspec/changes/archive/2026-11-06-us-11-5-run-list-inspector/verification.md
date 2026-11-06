# Verification — us-11-5-run-list-inspector

Change: us-11-5-run-list-inspector
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| List this workspace's runs | PASS (arranged) | `scripts/qualify_identity.py`, disposable stack, real browser. An owner whose workspace has no key, and one run inserted because admission would refuse it, reaches Runs from the navigation: one row, `Queued`, its goal and its link, though other workspaces hold many. After a reload no write request went out, and the run stayed `queued` at version 1. Axe found nothing |
| Inspect a run | PASS | A run finished by the scripted worker, with reasoning metadata arranged on every reply. The screen shows each call's role, tokens, `openrouter`, Terra's canonical ID, wire ID and `unknown` upstream, and the tool attempts and checkpoints, with counts equal to the route's. Neither the route's body nor the page holds that metadata, `channel_values`, `accumulated_output`, a key shape or the artifact's text. Axe found nothing |
| Refuse another workspace's run | PASS | Another owner gets 404 with none of the goal's text, the screen says it's not available, and it isn't in their list |

Checks on the final code: `fast` and `harness` exit 0. The identity qualifier's 342 cases pass, and `openspec validate` is clean.

## Findings

None.

## Limits

- **The list isn't paged.** It shows the newest 100 and says when there are more, and older runs have no screen yet.
- **Upstream provider reads `unknown` here** because the scripted model reports none. US-3.4 saw `null` from the real route too.
- **Costs, errors and evidence links are US-11.9's.**
- **The identity shown comes from the run's frozen snapshot,** then the current profile, and a retired profile with neither reads `unknown`. That last path wasn't exercised.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
