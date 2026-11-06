# Verification — us-11-7-approval-reason-target

Change: us-11-7-approval-reason-target
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Show the policy's reason and the target | PASS | `scripts/qualify_identity.py`, disposable stack, real browser, on requests created through the real gateway. The card shows `This tool changes something outside this Mac, so policy holds each call for a person.`, `Mail to team@example.invalid`, the exact arguments and the expiry. A request whose arguments say `REASON FROM THE MODEL` keeps the same reason, with that text only in the request. A unit test shows the connector's target coming from server configuration |
| Don't invent what wasn't recorded | PASS (arranged) | A pending request with both columns cleared, as a migration leaves one. The card says each is not recorded, and shows the request. A changed hash answers `409 approval_mismatch`, the view's hash is the one stored, and Reject through the card moves the run on |

Checks on the final code: `fast`, `harness` and `app_db.py qualify` exit 0, the identity qualifier's 347 cases pass, and `openspec validate` is clean.

## Findings

**`app_db.py qualify` caught drift.** The first run failed because `packages/db-types` lacked the two new columns. `app_db.py types` regenerated them, and it then passed.

## Limits

- **The reason is one sentence per kind of tool,** from its policy, so it doesn't explain a particular call. That's by design: nothing about the call can reach it.
- **A tool with no target of its own says not recorded,** including `workflow_approval`, whose reason is its own and whose target isn't set. A real workflow approval wasn't shown here.
- **The live connector wasn't exercised.** The configured repository's target is a unit test.
- **The persistent install wasn't migrated.** It stays at `20261106000032`, and this release's API can't read approvals there until `apply` runs. Only US-11.3 was authorized to change it.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
