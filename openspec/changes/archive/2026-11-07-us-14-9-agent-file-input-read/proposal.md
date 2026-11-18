## Why

US-14.9, [PRD-Tool-Catalog "File tools" and FI-01](../../../../docs/PRD/PRD-Tool-Catalog.md#file-tools) and Decision 0017 Q10 and Q11: a person can't attach files to a goal, `read_run_file` returns a whole file or fails past its cap, there's no CSV reader, and nothing can save a remote text file.

## What Changes

- **Agent File Input:** the goal composer attaches up to 5 plain text, markdown, JSON or CSV files of at most 1 MiB each, refusing others with a reason. They go with the run request as input documents under `inputs/`, which now carry a media type and may be 1 MiB. It is not a catalog tool. The BFF allows 12 MiB for `POST /v1/runs` only, for JSON escaping; every other route keeps 64 KiB.
- **`read_run_file` version 2:** line `offset` and `limit`, returning media type, version, sha256, total lines and a cut flag, capped at 200,000 characters. Version 1 stays registered: runs that pinned it keep it, and new grants pin 2 (the execution contract records 1→2 as compatible).
- **`read_csv`:** delimiter, header, `max_rows` up to 500 and a column choice, returning columns with inferred types (integer, number, boolean, date, string, empty), rows, the row count and a cut flag. A general tool.
- **`store_remote_file`:** a guarded download of a text file (plain, markdown, CSV, JSON) up to 1 MiB, saved under `outputs/` as a new version with an operation ID, a receipt and a readback. Expert-granted only, since it reaches the network.
- The URL guard also checks the connected peer's address before reading a body, against DNS rebinding, when the transport reports it.

## Capabilities

### New Capabilities

- `file-tools`: attached inputs and the file tools.

### Modified Capabilities

None.

## Impact

`apps/web/components/goal-composer.tsx`, `apps/web/lib/bff.ts`, `contracts/plans.py`, `contracts/tools.py`, `application/runs.py`, `application/tools.py`, `adapters/remote_files.py`, `adapters/url_guard.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, the generated contract and client, `tests/db/web_tools_check.py`, `tests/db/run_files_probe.py`, `tests/db/goal_loop_check.py` (plain goals now also get `read_csv`), the browser specs and unit tests. No migration.
