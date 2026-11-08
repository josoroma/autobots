# Verification — us-15-15-approval-gated-pull-request

Change: us-15-15-approval-gated-pull-request
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 4 of 4 tasks complete. 1 requirement added to `github-issue-connector`.
- **Transport:** every observation uses `tests/db/pull_request_check.py`. It runs the real gateway, approvals and receipts on a disposable database, in `python3.12 scripts/verify.py --profile db` (exit 0, 601 identity cases). A fake GitHub holds branches, commits, files and pull requests in memory, and no request reached GitHub.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **"The approval shows each file's diff":** a proposal changing `README.md` and adding `docs/new.md` on base `main` (head `base-1`) returned `approval_pending`. Its approval request, as `list_approvals` serves the approvals screen, holds:
  - the title in its arguments;
  - `review_detail` with base `main` at `base-1`;
  - a `modified` diff for the README (`-Hello`, `+Hello, reviewed`) and an `added` diff for the new file.
  
  Only reads had been sent. The approval detail renders each diff as a labelled, focusable region (type-checked and linted, not browser-tested).
- **"Bounded changes":** 21 files, two files of 600,000 bytes each, and a `repository` argument each got `invalid_arguments`, with no approval request and no request to GitHub.
- **"Branch, commits and marker":** once approved, the call succeeded and created branch `autobots/<operation_id>`.
  - Its commit's tree changed only `README.md` and `docs/new.md`.
  - The pull request's base was `main`, and its body held the operation-ID marker.
  - No merge request was sent, and the input has no merge field.
  - The operation ID is the gateway's, a hash in place of the scenario's illustrative `op_1`.
- **"A retry returns the existing pull request":** the fake created the pull request, then lost the reply, so the call was `unknown`. The retry read back with a single GET of the branch's open pull requests. It returned pull request 2 as a replayed success and wrote nothing, so exactly two pull requests exist in all.
- **"A moved base is refused":** after approval, the fake moved `main` to `base-2`.
  - The call failed with `base_moved`, with no writes and no new pull request.
  - The request returned to `pending` with `base_sha` `base-2` and a README diff from the upstream text (`-Hello, changed upstream`).
  - Asked again, it waited on that request. Approved again, it opened the pull request against `base-2`.
- **Also:** no receipt, approval or event of the run holds the token.
- **Found during verification, fixed before this record:** the first `db` run failed in the check's own re-approval step. A run doesn't wait again until the model asks again, so the check now makes that call first. Every scenario case had already passed in that run.
- **Regression:**
  - `fast` passed (exit 0).
  - `full` passed (exit 0, 38 browser tests).
  - `db` passed, including the existing connector, approval and effect checks with the gateway's new `review_detail` hook, which only this tool sets.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
