# Verification — us-15-14-github-read-tools-issue

Change: us-15-14-github-read-tools-issue
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-08

## Findings

- **Completeness:** 4 of 4 tasks complete. 1 requirement added to `github-issue-connector`.
- **Transport:** every observation below uses a fake GitHub transport (`httpx.MockTransport`). No request reached GitHub, and no token was used.
- **Order:** the planning artifacts were written after the implementation in this session. They describe what was built and were validated before verification.
- **"Read tools against a fake transport":** observed in `python3.12 scripts/verify.py --profile db` (exit 0), `tests/db/connector_check.py`, through the real gateway on a disposable database. Granted the four read tools, each call:
  - succeeded with no approval and no receipt;
  - sent requests only to `/repos/owner/throwaway/...`, plus `/search/issues` with `repo:owner/throwaway`;
  - was recorded as a `tool_uses` row in group `connectors`, `succeeded`, with no operation ID.
  
  `test_github_reads.py` (under `fast`) checks each output's fields:
  - pull requests: number, title, author, merged time, labels and URL;
  - workflow runs: ID, conclusion, times, head SHA, and failing jobs and steps;
  - issues: number, title, state, labels and URL;
  - files: path, ref, SHA, size and content.
  
  It also checks that every request is a GET to the configured repository, and that the search's `q` is `login repo:owner/configured is:issue state:open`.
- **"Bounded inputs, and no repository argument":** observed in `test_github_reads.py`, with no requests sent. These ten inputs are refused before any request:
  - a `repository` argument on two tools;
  - state `draft`, status `cancelled` and limits of 101;
  - `repo:` and `org:` in a search;
  - `../` and absolute paths.
  
  A file over 1 MiB fails as `github_file_too_large`, and no tool's input schema has a repository, owner or organization property.
  
  On the database, a read naming a repository got `invalid_arguments` with no new request.
- **"File content stays private":** observed in `connector_check.py`.
  - The read file's `output_public` holds path, ref, `sha` and `size`, with no content.
  - Neither its tool-use listing (`list_tool_uses`, which backs the run screens) nor the run's events contain the text.
  - `content` isn't a public output field.
- **"Labels on new issues, version 1 kept":** observed in `connector_check.py`.
  - With version 2, 11 labels got `invalid_arguments`, with no approval request and no request to GitHub.
  - 10 labels waited for approval, and once approved created the issue with exactly those labels.
  - Version 1, the grant of a run that pinned it, ran every earlier case unchanged: approval, the receipt marker, replay, uncertain outcomes settled by readback, and refusals. It sent only a title and body.
  - New grants get version 2. A grant naming version 3 is refused as `tool_not_registered`.
  - Interpretation: Expert versions don't hold tool versions. A run freezes its granted versions at admission, so "an Expert version that pinned version 1" is exercised as a run whose admitted grants name version 1, as `read_run_file` version 1 is kept.
- **"Key missing until both are set":** observed in `test_github_reads.py`.
  - With only `GITHUB_REPOSITORY`, only `GITHUB_TOKEN`, or neither, every GitHub tool is `key_missing` with `github_key_missing`, and both set is `available`.
  - In `python3.12 scripts/verify.py --profile full` (exit 0, 38 browser tests), `tools.spec.ts` showed all five GitHub tools, with no variables set, as "Unavailable: key not set". Their repair names both variables, the five permissions from Decision 0022 D6, and a restart of the worker and API, with no value.
  - The operations runbook lists the tools and permissions.
- **Regression:**
  - `fast` passed (exit 0, including 786 Python tests).
  - `full` passed.
  - `db` passed (exit 0, 585 identity cases).
  - `test_github_issues.py` and `test_tool_catalog.py` now expect version 2 for new grants and the five connector tools in the group. `boundary.spec.ts` expects the catalog's latest `create_github_issue@2`.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
