## Why

US-10.2's finding B3, and Decision 0009: a reviewer sees what a tool would do, but not why policy is asking or what it touches. The inbox shows the policy's reason, written by the server, not a model's.

## What Changes

- Approval requests store a policy reason and a resource target, set by the gateway from the tool's own definition.
- The approval view returns both, and the inbox shows them with the exact action and expiry.
- A request saved before these existed says which is not recorded, and nothing fills them in.

## Capabilities

### New Capabilities

- `approval-context`: what a reviewer is shown about why an approval is asked and what it touches.

### Modified Capabilities

None.

## Impact

A migration on `public.approval_requests`, `application/tool_gateway.py`, `application/approvals.py`, `contracts/approvals.py`, `api/approval_routes.py`, `application/workflow_runner.py`, `adapters/github_issues.py`, generated clients, the inbox and tests. **The persistent install needs this migration applied before it runs this code,** and that isn't done here, since only US-11.3 was authorized to change it.
