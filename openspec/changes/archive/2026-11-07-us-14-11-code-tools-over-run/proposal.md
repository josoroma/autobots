## Why

US-14.11, [PRD-Tool-Catalog "Code tools"](../../../../docs/PRD/PRD-Tool-Catalog.md#code-tools) and Decision 0017 C7 and Q8: the request asked for a ripgrep-style `search_files` with read, write and patch, modelled on Hermes Agent. Autobots grants no shell, and arbitrary execution stays disabled, so they work on the run's own files.

## What Changes

- `search_files`: a regular expression over the latest version of each run file the scope's path grants cover, with a path prefix, a glob, `content`/`files_only`/`count` modes, up to 5 context lines, `limit` up to 200 and `offset`; match lines capped at 500 characters; `invalid_pattern` for a pattern that doesn't compile. Pure Python, run in a thread so the gateway's timeout bounds it.
- `read_code_file`: numbered lines with offset and limit (up to 2000), total lines and a cut flag.
- `write_code_file` and `patch_code_file`: under `outputs/` only, by schema, as new versions with an operation ID, a receipt and a readback. A patch is exact replacement: `old_string_not_found`, or `old_string_ambiguous` without `replace_all`, writes nothing.
- Names never match the SDK's own file tools. They join the execution contract and the Expert-grantable set, in the code group; plain goals don't get them.

## Capabilities

### New Capabilities

- `code-tools`: code tools over run files.

### Modified Capabilities

None.

## Impact

`application/code_tools.py`, `contracts/code_tools.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, `tests/test_code_tools.py` and `tests/db/web_tools_check.py`. No binary, no package.
