# github-issue-connector Specification

## Purpose
Let a granted run create an issue in one configured GitHub repository, under the same approval, credential and uncertain-outcome rules as any consequential tool.

## Requirements

### Requirement: Enforce the selected connector contract

An authorized call on the selected connector SHALL follow the registered tool contract for its schema, credentials, permissions, idempotency and uncertain outcomes.

#### Scenario: Enforce the selected connector contract

- **GIVEN** an explicitly selected service and allowed operation with versioned scopes and approval policy
- **WHEN** the connector performs an authorized call
- **THEN** schema, credentials, permissions, idempotency and uncertain-outcome behavior follow the registered tool contract

### Requirement: Reject out-of-scope work

An operation outside the connector's grant SHALL be rejected by the policy gateway before any external effect.

#### Scenario: Reject out-of-scope work

- **GIVEN** the selected connector receives an operation outside its grant
- **WHEN** execution is requested
- **THEN** the policy gateway rejects it before an external effect

### Requirement: Read-only GitHub tools and issue labels on the one configured repository

The four GitHub read tools SHALL work only on the configured repository, with bounded inputs and no repository input, recorded as read-only tool uses. `github_read_file` content SHALL never appear on run screens. `create_github_issue` version 2 SHALL accept up to 10 labels while version 1 is unchanged. Every GitHub tool SHALL read `key_missing` until both variables are set, with a repair naming them, the token's scopes and a restart.

#### Scenario: Read tools against a fake transport
- **GIVEN** GITHUB_REPOSITORY and a fake GITHUB_TOKEN set, a fake GitHub transport, and an Expert granting the four read tools
- **WHEN** the model calls github_list_pull_requests, github_list_workflow_runs, github_search_issues and github_read_file with allowed inputs
- **THEN** each returns validated output with the fields its requirement lists, every request targets only the configured repository, the search is restricted to it, and each call is recorded as a read-only tool use

#### Scenario: Bounded inputs, and no repository argument
- **GIVEN** the same tools on a fake transport
- **WHEN** a call names a repository, a state outside its allowed set or a limit above 100, and when github_read_file meets a file over 1 MiB
- **THEN** the first three are refused before any request, the oversized file fails with a typed code, and no tool schema offers a repository input

#### Scenario: File content stays private
- **GIVEN** a github_read_file call that returns text
- **WHEN** its tool use is listed and the run's screens render it
- **THEN** the content appears only as a digest and size, with its SHA and size, and never as text

#### Scenario: Labels on new issues, version 1 kept
- **GIVEN** create_github_issue version 2, an Expert version that pinned version 1, and a fake transport
- **WHEN** version 2 is approved and called with 10 labels, version 2 is proposed with 11 labels, and version 1 is approved and called with a title and body
- **THEN** the first creates the issue with those labels, the second is refused before any approval request or request to GitHub, and version 1 behaves as before

#### Scenario: Key missing until both are set
- **GIVEN** only one of GITHUB_REPOSITORY and GITHUB_TOKEN set
- **WHEN** the catalog is read
- **THEN** every GitHub tool reads key_missing, and the repair names both variables, the token's scopes and a restart, and never a value

### Requirement: An approval-gated pull-request connector on the configured repository

`github_open_pull_request` SHALL wait for approval on every call, showing the title, base branch and each file's diff against the base head, with no write before approval. It SHALL refuse more than 20 files, more than 1 MiB and any repository argument before any approval or request. Once approved, it SHALL create `autobots/<operation_id>`, commit only the named paths, open the pull request with the operation-ID marker and offer no merge, read back before any retry, and stop with `base_moved` when the base head moved, returning the request to a new approval against the new head.

#### Scenario: The approval shows each file's diff
- **GIVEN** an Expert granting github_open_pull_request and a fake transport that holds the base branch
- **WHEN** the model proposes a pull request with a title, body, base branch and file changes
- **THEN** the run waits for approval, the request shows the title, the base branch and each file's diff against the base, and no request that writes has been sent

#### Scenario: Bounded changes
- **GIVEN** proposals with 21 files, with more than 1 MiB in total, and with a repository argument
- **WHEN** each is validated
- **THEN** each is refused with a typed code before any approval request or request to GitHub

#### Scenario: Branch, commits and marker
- **GIVEN** an approved proposal whose operation ID is op_1, on a fake transport
- **WHEN** the connector runs
- **THEN** it creates the branch autobots/op_1, commits only the named paths, opens the pull request with op_1 as a marker in its body, and offers no merge

#### Scenario: A retry returns the existing pull request
- **GIVEN** an approved call whose pull request was opened but whose response was lost, on a fake transport
- **WHEN** the worker retries
- **THEN** it first reads back the branch and any open pull request from it, returns the existing pull request, and opens no second one

#### Scenario: A moved base is refused
- **GIVEN** an approved pull request and a fake transport whose base branch head has moved since approval
- **WHEN** the connector runs
- **THEN** it stops with base_moved, opens nothing, and a new approval shows the diff against the new head

### Requirement: An owner-authorized live qualification of the Studio GitHub tools

The GitHub qualification runner SHALL qualify the four read tools, labelled issues and the pull-request connector once against the configured repository. It SHALL run only with the owner's token in the environment it is given and a recorded authorization naming that repository and a request cap. It SHALL count each request before sending and send none beyond the cap. It SHALL open the pull request only after the owner approves its diff, and SHALL record a redacted report that holds no token. It SHALL be in no verification profile.

#### Scenario: One live pass per tool on the owner's repository
- **GIVEN** the owner's fine-grained token for josoroma/bot-test in the worker environment and the owner's capped authorization
- **WHEN** the qualification runner calls each read tool, creates one labelled issue, and opens one pull request after approval
- **THEN** each returns validated output from GitHub, the issue and the pull request carry their operation markers, a retry of the pull request returns the existing one, and the redacted record holds no token

#### Scenario: Not run without the owner
- **GIVEN** no recorded authorization or no token in the environment
- **WHEN** the runner starts
- **THEN** it refuses before any request to GitHub
