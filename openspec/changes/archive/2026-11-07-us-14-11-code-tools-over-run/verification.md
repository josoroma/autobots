# Verification — us-14-11-code-tools-over-run

Change: us-14-11-code-tools-over-run
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 4/4 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed through the gateway on a disposable stack, with the search also tested on its own |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Search run files | PASS | `tests/db/web_tools_check.py`, run by `scripts/app_db.py` in the `db` profile: with another run holding `inputs/secret.py` that also contains `def main`, a search for `def \w+|main` under `inputs/` and `*.py` with one context line returns only this run's `inputs/app.py`, lines 3 and 5, with the blank line before and `return os.getcwd()` after line 3, and line 5 (700 characters) cut to 500; a count finds 2; a file search finds both `app.py` files; `(unclosed` fails `invalid_pattern`. `services/agent/tests/test_code_tools.py` covers prefix, glob, `files_only`, `count`, file-name target, paging with the truncation flag on and off, and schema ceilings for an empty pattern, 6 context lines, limit 201 and a 201-character pattern |
| Patch exactly or not at all | PASS | Same check: on `outputs/app.py` (version 1, written by `write_code_file`), an absent `old_string` fails `old_string_not_found` and one found twice without `replace_all` fails `old_string_ambiguous`, with the file still at one version; an exact patch makes version 2 with a sha256 and 1 replacement, and `replace_all` makes version 3 with 2 replacements, leaving `x = 9`, `x = 9`, `y = 3` |
| Writes stay under outputs/ | PASS | Same check: `write_code_file` to `inputs/app.py` and to `../etc/passwd`, and `patch_code_file` on `inputs/app.py`, are each denied `invalid_arguments`, and the run's inputs are unchanged. `read_code_file` returns lines 3 and 4 of 5, numbered, with `truncated: true`. The unit test confirms no code tool is named like an SDK file tool |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the code tool cases, `identity_qualification`, `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed |
| `openspec validate us-14-11-code-tools-over-run` | 0 | valid |

## Findings

**Found and fixed:** two expected counts in the first unit test were mine and wrong ("main" is on four lines, two under `inputs/`).

## Limits

- A pathological pattern runs in a worker thread; the gateway's 10-second timeout returns `tool_timeout`, but Python can't stop the thread, which runs to its end.
- A patch reads the latest version, then writes under the path's lock, so two concurrent patches could both apply to the same base. One run's tool calls are serialized by the gateway middleware, so this needs two runs writing one run's file, which scopes don't allow.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
