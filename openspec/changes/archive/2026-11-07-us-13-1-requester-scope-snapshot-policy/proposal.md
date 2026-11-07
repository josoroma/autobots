## Why

US-13.1, PRD 9.2 and LC-10: an approval request doesn't yet record who asked, under what scope or under which policy version (review findings N-22, N-24 and N-25). [Decision 0015](../../../docs/engineering/decisions/0015-approval-request-fields.md) says what each field holds.

## What Changes

- A run records the person who started it, at admission. A child run takes its parent's person. A routine's run records no person.
- An approval request stores, as immutable fields alongside its argument hash:
  - the **requester**: that person, and the proposing agent (an Expert's ID and version, or the coordinator);
  - the **scope snapshot**: the granted tools with their versions, and the granted paths, which hash to the stored `scope_hash`;
  - the **policy version** (`approval-policy/1`) and the rule that fired.
- A database trigger refuses any later change to these fields, including filling them in on an older request.
- The approval view returns them, and the inbox shows them below the reason and target. A request saved before them shows each as not recorded.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `approval-context`: a reviewer is also shown the requester, scope snapshot and policy version.

## Impact

A migration on `public.runs` and `public.approval_requests`. Also `application/runs.py`, `application/workflows.py`, `application/approvals.py`, `application/tool_gateway.py`, `application/operations.py`, `contracts/approvals.py`, `api/approval_routes.py`, `api/run_routes.py`, `api/workflow_routes.py`, the generated contract and clients, the inbox, `tests/db/approval_check.py` and the approvals browser spec. **The persistent install needs this migration applied before it runs this code.** That isn't done here, as Decision 0015 authorizes no persistent change.
