## Why

US-15.14, [PRD-Studio GH-01 to GH-05 and GH-07](../../../PRD-Studio.md#github-tools) and [Decision 0022 D6 and D12](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision). The only GitHub tool creates an issue. The concepts' Experts must triage issues, read CI failures, list pull requests and read files on the same one repository, and label new issues.

## What Changes

- Four read-only tools in `adapters/github_reads.py`, plain `httpx` with an injectable transport, over the shared `configured_target` and `github_client`:
  - `github_list_pull_requests`: state open, closed or merged; base; since; limit up to 100.
  - `github_list_workflow_runs`: workflow file, branch, status failure or success, since, limit. Each failed run includes its failing jobs and steps.
  - `github_search_issues`: text and state. The query is pinned to the repository, and `repo:`, `org:`, `user:` and `owner:` qualifiers are refused.
  - `github_read_file`: path and ref. Text up to 1 MiB, otherwise `github_file_too_large`. The content is not a public field, so a tool use keeps only its SHA and size.

  No input names a repository, and each needs no approval.
- `create_github_issue` version 2 adds optional `labels`, up to 10. New Expert grants get version 2. Version 1 stays registered and unchanged, so a run whose admitted grants pinned it keeps calling it. The execution contract records `create_github_issue` 1 to 2 as compatible.
- `KeyRequirement` and the catalog's `KeyRequirementView` carry the credential's `scopes`. GitHub's are Decision 0022 D6's fine-grained permissions.
  - Every GitHub tool is `key_missing` until both `GITHUB_REPOSITORY` and `GITHUB_TOKEN` are set.
  - Tools' repair names both variables, the permissions and a restart, never a value.
- The operations runbook's GitHub section lists the tools and those permissions.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-issue-connector`: the read tools, issue labels and key repair.

## Impact

- `adapters/github_issues.py`, the new `adapters/github_reads.py`, `contracts/tools.py`, `domain/tool_catalog.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py` and `application/tool_catalog.py`.
- The generated contract and client.
- `tool-catalog.tsx` (repair).
- Tests:
  - `test_github_reads.py`;
  - updated `test_github_issues.py` and `test_tool_catalog.py`;
  - extended `tests/db/connector_check.py`;
  - `tools.spec.ts` and `boundary.spec.ts`.
- `docs/engineering/runbooks/operations.md`.
- Every test uses a fake transport. No call reaches GitHub.
