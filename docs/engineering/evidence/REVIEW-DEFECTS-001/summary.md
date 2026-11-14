# REVIEW-DEFECTS-001: the four small defects the code-quality review ranks first

**Date:** 2026-11-14. **Status:** done, not committed. **Scope:** a fix the owner asked for ("Fix the four small defects the review ranks first"), outside the OhMyOrch delivery loop. This short record follows DH-W01–06. The defects and plan items come from [the code-quality review](../../../reviews/review-2026-11-12-09-52-30/README.md), a static review, not acceptance evidence.

## Plan

| Finding | Plan item | Defect |
|---|---|---|
| [WSYS-01](../../../reviews/review-2026-11-12-09-52-30/findings/web-system.md#wsys-01) | [R-13](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-13) | Operations read retention days with `Number.parseInt`, so "1,000" saved as one day ahead of an irreversible retention pass. |
| [PADP-01](../../../reviews/review-2026-11-12-09-52-30/findings/py-adapters.md#padp-01) | [R-14](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-14) | Malformed `save_artifact` arguments made the live-result tap raise inside the stream loop, which reads as `partial_stream` and stops a paid run. Decision 0022 D4 says a tap failure never stops the run. |
| [XDUP-01](../../../reviews/review-2026-11-12-09-52-30/findings/sweep-duplication.md#xdup-01), [PRUN-05](../../../reviews/review-2026-11-12-09-52-30/findings/py-run.md#prun-05) | [R-15](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-15) | Text shown to workspace members masked only three secret shapes, while logs also masked Decision 0017's tool keys, credentialed URLs and key-value credentials. SP-011 allows display redaction only to get stricter. |
| [WTAP-02](../../../reviews/review-2026-11-12-09-52-30/findings/web-tools-approvals.md#wtap-02) | [R-16](../../../reviews/review-2026-11-12-09-52-30/refactor-plan.md#r-16) | AP-04's two-press shortcut counted a held key's repeated keydown as the second press, let Alt chords decide, and kept an arm with no request id. |

Tests come first for each. Left out on purpose: R-01 (every test file selected by glob) and R-15 step 4 (a parity test for `scripts/evidence.py`'s own patterns). Instead, the two new web unit test files are added by name to `web_unit_tests`.

## Implementation

- **Retention days (R-13).** `apps/web/lib/retention.ts` `parseDays` accepts an empty window or ASCII digits only. `operations-panel.tsx` checks each field's range with the generated `parseRetentionSettings`, sends nothing when either field is refused, and marks the field with `aria-invalid` and an inline message. A 422 shows the pairing rule; other refusals show the service's message, or "didn't answer" on a network failure.
- **Approval shortcut (R-16).** `apps/web/lib/approval-shortcut.ts` holds `chord` (⌘ or Ctrl, never Alt) and `press` (ignores `event.repeat`, binds the arm to one approval id). `approvals-panel.tsx` uses them.
- **Live-result tap (R-14).** In `adapters/result_stream.py`, `flush` ends only a malformed call's live text on `ValueError`. `feed`, `finish` and `close` never raise; any other failure disables the tap and logs `result_text.unavailable` or `result_text.close_failed`. The reply still settles the malformed call as an invalid tool call.
- **Secret shapes (R-15).** `domain/secret_patterns.py` holds one list of shapes, matched separately on the original text with the spans merged. A named credential masks only its value, after an optional quote and an optional Bearer, Basic or Token scheme. Logs (`operations/logs.py`) end a value at whitespace and also mask a key inside a word. Shown text (`public_text`) ends a value at a quote or at the next `name=` parameter, so redacted approval JSON still parses.
- **Checks.** `scripts/verify.py` adds the two new web unit test files to `web_unit_tests`, which lists files by name.
- **Tests.** New unit tests in `apps/web/tests/unit/` and `services/agent/tests/`, and browser cases in `operations.spec.ts` and `approvals.spec.ts`. The Python cases for R-14 and R-15 failed before the fix and pass after.
- `CODEBASE.md` lists the new domain module.

No contract, migration, configuration or dependency changed.

## Review

An independent read-only reviewer (`autobots-reviewer`) inspected the full diff twice.

- **Round 1: changes needed.** One blocking finding: "Authorization: Bearer <token>" showed the token, because the key-value shape stopped at the scheme. One should-fix: a masked value swallowed JSON punctuation, so approval arguments stopped parsing. Five notes: overlapping shapes, a timing window in the held-key check, a stale arm message, retention copy, and an unguarded `close()`.
- **Round 2: approve**, on the diff whose sha256 starts `9fecf1daac775fde`. All earlier findings were resolved or accepted. Its timing note was then applied as the reviewer suggested: the held-key check now asserts that the announcement is still arming or has lapsed, which a decision would have cleared.

## Verification

| Check | Exit | Observed |
|---|---|---|
| `services/agent`: ruff, ruff format, mypy over 140 files, pytest | 0 | Passed, 923 tests |
| `node --test` on the two new web unit files | 0 | Passed, 20 tests |
| `python3.12 scripts/verify.py --profile fast` | 0 | Passed, after the last source edit and after the last test edit |
| `python3.12 scripts/verify.py --profile db` | 0 | Passed: identity 169 passed and 0 failed, including "a malformed or out-of-range retention window is refused on the page, and nothing is sent" and "a shortcut needs a second press, and never acts while typing" |
| `python3.12 scripts/verify.py --profile harness` | 0 | Passed, after this record |

An earlier `db` run passed every qualification but failed its non-mutation guard, because this record and `CODEBASE.md` were edited during the run. It is superseded by the run above.

## Runbook

Operating behavior is unchanged, so no runbook changed. The `db` profile is the regression check for the two screens.

## Limits

- Shown text still reveals what follows an apostrophe, an escaped quote or a `&name=` inside a secret value, and a credential-named JSON field with a non-string value loses its structure. Both are stricter than before, when shown text masked none of these shapes.
- An unknown authorization scheme, such as `Digest` or `ApiKey`, still leaves its credential visible, in logs and on screen, as before.
- The arm's announcement can stay on screen for up to 2 s after the selection changes. The arm itself can no longer decide another request.
- Not done: R-01 (selecting test files by glob) and R-15 step 4 (a parity test for `scripts/evidence.py`'s own patterns).
- Static, mock and disposable evidence only. Nothing was checked on the persistent install, which needs a rebuild of the web app and a restart of the service.
