# Verification — us-15-16-live-github-qualification-configured

Change: us-15-16-live-github-qualification-configured
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Summary

| Dimension    | Status |
|--------------|--------|
| Completeness | 4/4 tasks, 1 requirement |
| Correctness  | 1/1 requirement, 2/2 scenarios observed |
| Coherence    | Followed. No design.md, so Design Adherence is not applicable |

## Scenario: One live pass per tool on the owner's repository — PASS (live)

**Command:**

```
PYTHONPATH=services/agent/src services/agent/.venv/bin/python scripts/qualify_github_connector.py --live --suite studio --env-file .env --authorization openspec/changes/us-15-16-live-github-qualification-configured/authorization.json --phase review
```

It was then run again with `--phase apply --approved-review .checks/github-studio/review.json`, after the owner approved the diff in the delivery session. Apply exited 0 at 2026-11-08T15:21:03Z.

**Target and preconditions:**
- **Repository:** `josoroma/bot-test`. Both probes found it private, with a fine-grained token that reports no classic scopes.
- **First commit:** the repository had no commits, and the first review stopped on GitHub's 409 before writing anything. By the owner's added authorization, one request created `README.md` on `main` (`3301fb4d8235`). The second review computed the diff against that head: one added file, `qualification/us-15-16-867d47c8.md`.

**What came back** (shapes only, from the redacted `.checks/github-studio/qualification.json`):
- **Read tools:** each output was validated again against its contract.
  - `github_list_pull_requests`: `{pull_requests: 0 items}`. No closed PRs existed yet.
  - `github_list_workflow_runs`: `{runs: 0 items}`. The repository has no Actions.
  - `github_search_issues`: `{issues: 2 items}`.
  - `github_read_file`: path, ref, sha, size and content. It read the committed file back from the PR branch, equal to the approved content.
- **`create_github_issue` version 2:** opened issue #3, carrying the label `documentation` and its operation marker.
- **`github_open_pull_request`:**
  - opened PR #4 from `autobots/qualification-54932265867d47c8` with its operation marker;
  - base `main` at the approved `3301fb4d8235`;
  - changes only the approved path, and it isn't merged.
- **Retry and readback:** a second handler call returned PR #4, and the connector's readback found PR #4. No second PR was opened, and nothing returned the approval to review.
- **Cleanup:** PR #4 was closed (200), its branch deleted (204), and issue #3 closed (200).

**Cap:** 30 of the 40 authorized requests, counted in a ledger kept between runs: 21 GET, 5 POST, 2 PATCH, 1 PUT and 1 DELETE.
- The 30 include 2 from the first review, which stopped on the 409.
- They also include the 1 owner-authorized README write.
- No model call was made.

**Token:** the runner refused to save any record holding the token, and saved all three: `qualification.json`, `review.json` and `requests.json`. After writing this file, a check against the env file's value found the token absent from it too.

## Scenario: Not run without the owner — PASS (offline, arranged)

`.checks/us-15-16/refusals.py` runs the runner with every socket connection blocked and recorded. Each of these exits 2 with 0 connection attempts:
- no `--live`;
- no recorded authorization;
- no token in the env file;
- no env file;
- an authorization naming another repository;
- no `--authorization`;
- apply without the approved review.

## Also exercised (fake transport, before any live request)

`.checks/us-15-16/dry_run.py` runs both phases against a stateful fake GitHub:
- A full pass used 27 requests, and both its PR and its issue were closed and its branch deleted. No record held the token.
- A public repository and a classic broad token are each refused after a single probe GET.
- A pass whose ledger leaves too few requests stops with a failed cap case, stays within 40 and still closes what it made.

## Findings

- **WARNING:** `github_list_workflow_runs` returned no runs, because the repository has no Actions workflows. Its failing-jobs path was exercised only on fakes, in US-15.14.
- **SUGGESTION:** the issue and the pull request are closed, not deleted, since GitHub can't delete them through this token's permissions. The `README.md` commit stays on `main`, as the owner authorized.
- **Not established:**
  - H1 and product acceptance.
  - The gateway, the approvals table and the worker on this path: the runner calls the tools directly, and `tests/db/pull_request_check.py` covers that path on fakes.
  - A real lost reply, and a moved base live: both are covered only by fakes.
