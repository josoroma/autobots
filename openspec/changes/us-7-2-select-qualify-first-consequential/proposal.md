## Why

US-7.2 needs one specifically selected connector, so external automation is verified against an actual destination's contract. [Decision 0007](../../../docs/engineering/decisions/0007-first-connector-github-issues.md) selects creating an issue in one configured GitHub repository.

## What Changes

- A `create_github_issue` tool under the existing effect contract: consequential, so every call needs approval first, with no retries and a recorded receipt.
- The repository comes from server configuration, never from the model, and the token is read per attempt and stored nowhere.
- GitHub has no idempotency key here, so each issue carries a marker with its operation ID, and an uncertain outcome is settled by reading the repository's issues back.
- An owner grants the tool per Expert. Goals without an Expert don't get it.
- A live qualifier for a throwaway private repository, which refuses a broad token or a public repository.

## Capabilities

### New Capabilities

- `github-issue-connector`: the selected connector's scope, approval, credential and uncertain-outcome behavior.

### Modified Capabilities

None.

## Impact

`services/agent/src/autobots/adapters/github_issues.py`, `contracts/tools.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, the Expert editor's tool list, `scripts/qualify_github_connector.py`, `tests/db/connector_check.py`, `scripts/qualify_identity.py`, `.env.example` and the operations runbook. New outbound calls to `api.github.com`, only when an owner grants the tool, configures it and approves a call.
