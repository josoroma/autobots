# Verification — us-14-9-agent-file-input-read

Change: us-14-9-agent-file-input-read
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Summary

| Dimension | Status |
|---|---|
| Completeness | 7/7 tasks, 3 reqs |
| Correctness | 3/3 scenarios observed on a disposable stack: one in the browser with real Auth, two through the gateway and the tool-use record with a fake transport |
| Coherence | Followed the proposal. No design.md |

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Attach files to a goal | PASS | `apps/web/tests/browser/run-workspace.spec.ts` "US-14.9", run by `scripts/qualify_identity.py` in the `db` profile: five files (`.txt`, `.md`, `.json`, `.csv`, and `more notes.txt` as `inputs/more-notes.txt`) attach with their media types; a sixth is refused "only 5 files can be attached"; after removing one, a 1 MiB + 1 byte file is refused "a file can be at most 1 MiB" and a PDF "only plain text, markdown, JSON or CSV can be attached"; axe finds no violation. Running the goal stores exactly four inputs, read back from the database by `tests/db/run_files_probe.py`: `inputs/data.json` `application/json` 8 bytes, `inputs/notes.txt` `text/plain` 11, `inputs/plan.md` `text/markdown` 6, `inputs/rates.csv` `text/csv` 26. The catalog's Files group stays `publish_artifact`, `read_csv`, `read_run_file`, `save_artifact`, `store_remote_file`. `tests/db/web_tools_check.py` also shows admission storing each document's media type |
| Read run files in pages | PASS | `tests/db/web_tools_check.py`, run by `scripts/app_db.py` in the `db` profile: `read_run_file` 2 with offset 10 and limit 5 returns lines 10 to 14 of 30, `text/markdown`, version 1, a sha256 and `truncated: true`; `read_csv` with `max_rows` 2 returns columns typed string, number, boolean and date, two rows, a row count of 3 and `truncated: true`; `max_rows` 501 is refused `invalid_arguments`. Their tool-use records hold the path, version, sha256 and sizes, and no line text or row value. A grant pinned to version 1 still gets version 1's whole-file output |
| Store a remote file through the guard | PASS | Same check: a guarded `text/csv` URL is stored as `outputs/rates.csv` version 1, 26 bytes, with a sha256. An `http` URL fails `url_scheme_refused`, `127.0.0.1` `url_host_refused`, a PNG `media_type_refused`, a body over 1 MiB `url_too_large`, and a path under `inputs/` is denied `invalid_arguments`; the run then holds one file under `outputs/`, and the fake transport never saw the refused URLs |

## Checks run on the final code

| Check | Exit | Result |
|---|---|---|
| `python3.12 scripts/verify.py --profile fast` | 0 | ruff, mypy, pytest, lint, typecheck, contract drift, API client and web unit tests passed |
| `python3.12 scripts/verify.py --profile db` | 0 | `app_db_qualification` with the file cases, `identity_qualification` (main suite with the attachment test, and the visual, keyboard and zoom suites), `non_mutation_guard` and the rest passed |
| `python3.12 scripts/qualify_web.py` | 0 | 37 browser tests passed |
| `openspec validate us-14-9-agent-file-input-read` | 0 | valid |

## Findings

**Found and fixed:**
- The first identity run failed four existing checks after the composer change: attachments placed between the goal and the model choice broke the pinned keyboard order and made focus jump upward, the native file input measured as a raw control with a 1.3:1 boundary, and it overflowed 16px at 400% zoom. Attachments now follow the model choice in the right column, and the input uses the design system's `Input`.
- The web qualifier then found two home-page tests resolving two `role="status"` elements. The refusal region is now a plain polite live region.
- Two expectations were mine: the stored CSV is 26 bytes, and plain goals now also get `read_csv`, so `tests/db/goal_loop_check.py` lists eight tools.

## Limits

- `store_remote_file`'s peer check runs only when the transport reports the connected address; the fake transport doesn't, so that branch wasn't exercised here.
- No PDF, DOCX or XLSX conversion, by Decision 0017 Q11.
- **Not established:** H1 or product acceptance. No independent review ran, under Decision 0003.
