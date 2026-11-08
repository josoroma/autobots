# Tasks

## 1. Connector (Bounded changes; Branch, commits and marker)

- [x] 1.1 Add `github_open_pull_request` as a consequential connector with approval on every call, limits of 20 files and 1 MiB in total, and no repository input

## 2. Approval (The approval shows each file's diff; A moved base is refused)

- [x] 2.1 Compute each file's diff against the base head for the approval request, binding the approval to that head, and return a moved base to a new approval

## 3. Effect (Branch, commits and marker; A retry returns the existing pull request)

- [x] 3.1 Create `autobots/<operation_id>`, commit only the named paths, open the pull request with the marker, and read back the branch and pull request before any retry

## 4. Coverage

- [x] 4.1 Cover the scenarios with fake transports only, including a lost response, in `tests/db/pull_request_check.py` on a disposable database
