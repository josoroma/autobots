## Why

US-15.15, [PRD-Studio GH-06](../../../../docs/PRD/PRD-Studio.md#github-tools) and [Decision 0022 D6, D7 and D15](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). Code changes can't leave a run except as files. An Expert should be able to propose a pull request that a person approves with its full diff, and that is safe to retry.

## What Changes

- `github_open_pull_request` (version 1) is a consequential connector with approval on every call:
  - inputs are a title, body, base branch and up to 20 files' full new content, 1 MiB in all;
  - no input names a repository, each path appears once, and nothing climbs out of the repository.
- `ToolDefinition.review_detail` is a read-only hook the gateway calls before an approval request exists. Here it reads the base branch's head and each file there, and stores `{base_branch, base_sha, files: [{path, change, diff}]}` in the new `approval_requests.review_detail` column. `ApprovalView.review_detail` returns it, and the approval detail shows each diff.
- Once approved, the connector:
  - checks the base head still equals the approved `base_sha`;
  - creates `autobots/<operation_id>` from a commit whose tree changes only the named paths;
  - opens the pull request with the operation-ID marker.
  
  It offers no merge.
- If the head moved, it stops with `base_moved` and writes nothing. The request returns to pending with a diff against the new head. The failed attempt is marked ruled, so the next approval sends against that head.
- Readback finds the branch's open pull request, so a retry after a lost reply returns it and opens no second one.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-issue-connector`: the approval-gated pull-request connector.

## Impact

- New `adapters/github_pulls.py`.
- `application/tool_gateway.py` (`review_detail`), `application/approvals.py`, `api/approval_routes.py`, `contracts/approvals.py` and `contracts/tools.py`.
- `domain/tools.py`, `domain/execution.py` and `application/goal_loop.py`.
- A migration, the generated contract, client and row types, and `approvals-panel.tsx`.
- The new `tests/db/pull_request_check.py` with a stateful fake GitHub, and `test_tool_catalog.py`.
- Every test uses a fake transport.
