## Why

US-15.16, [Decision 0022 D6, D7 and D12](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#decision) and its [live authorization](../../../docs/engineering/decisions/0022-studio-product-surfaces.md#live-authorization). The read tools, issue labels and pull-request connector have only been seen working on fake transports. The owner has set a fine-grained token for `josoroma/bot-test` and authorized one capped live pass.

## What Changes

- `scripts/qualify_github_connector.py` gains a `studio` suite. Like US-7.2's suite, it is in no verification profile and refuses without `--live`.
- The suite refuses before any request to GitHub without:
  - both `GITHUB_REPOSITORY` and `GITHUB_TOKEN`, read only from the given env file into the runner's own process and never printed;
  - the recorded authorization in this change's `authorization.json`, which must name that repository.
- Every request goes through a counting transport, which refuses to send once the authorization's 40 requests are used, across both phases.
- **Phase `review`:** checks that the repository is private and the token has no classic scopes. It computes the pull request's approval detail through the connector's own `review_detail`, which only reads, and saves it for the owner.
- **Phase `apply`:** runs only with the review the owner approved. In order, it:
  - calls each read tool once, checking each output against its contract;
  - creates one issue with the `documentation` label through `create_github_issue` version 2;
  - opens the pull request against the approved `base_sha` through the connector's handler, retries it and reads it back;
  - closes the issue and the pull request, and deletes the branch.
- The redacted report goes to the ignored `.checks/github-studio/`. A summary is kept in this change's `verification.md`. The runner checks that neither file holds the token.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `github-issue-connector`: a live, owner-authorized qualification of the Studio GitHub tools.

## Impact

- `scripts/qualify_github_connector.py` only. Product code doesn't change.
- Live GitHub requests to `josoroma/bot-test`, within the recorded cap. No model call and no database.
