## ADDED Requirements

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
