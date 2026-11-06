# Verification — us-12-2-close-what-test-can

Change: us-12-2-close-what-test-can
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-06

## Scenarios

| Scenario | Result | Observed in |
|---|---|---|
| Inspect the goal after a compaction | PASS, in two halves | `slice-closure.spec.ts`, disposable stack, real browser: a run compacts with a scripted model, shown by summarizer calls on its ledger, and the page shows the same goal and criteria before and after. The real SDK on a fake transport is `qualify_worker_inference.py`, which compacted three times, and compares them through the API, not a browser. No one case does both |
| Return partial results across descendants | PASS | `tests/db/assignment_check.py`, real database, scripted model: a limit of 8 calls across the tree stops at 8, and the finished child's outcome and published artifact stay readable |
| See delegation on the Assignments card | PASS | `slice-closure.spec.ts`, scripted worker: the card shows the child's Expert and `succeeded`, its link opens the child, and the child links back. That back link didn't exist, and was added |
| Rebuild across a disconnect | PASS (arranged) | `slice-closure.spec.ts`. `tests/db/browser_runs.py` arranges a run with a plan, a published artifact and a pending approval. The browser goes offline, the page reads reconnecting, a cancel commits through Node, and back online the plan, artifact, approval and new status are all there, with event sequences unique and consecutive |
| Use local files with no key | PASS (arranged) | `slice-closure.spec.ts`: an owner with no key sees the arranged run's artifact, downloads its bytes, and a new run answers `409 credentials_required`. The fake upstream's log holds no chat call. Through the API and page on a disposable stack |
| Inventory each dispatch | PASS | `qualify_worker_inference.py`, real SDK on a fake transport: the ledger reads executor 11 and summarizer 3, both on Terra's route and the frozen role map, and 14 requests reached the fake transport for 14 rows, so a request off the ledger would fail it. A child's calls are checked by its own case, on the root's ledger |
| Check the shape of Terra's requests | PASS | The same run: 19 requests, no unadvertised flag, and `tests/harness/test_final_review.py` shows the check failing on a sampler flag, a parallel-tool flag and reasoning off or malformed |
| Walk each surface in both themes | PASS | `slice-visual.spec.ts`, 42 captures, retained in `docs/engineering/evidence/US-12.2/`: 9 to 60 keyboard stops in document order, 12 disabled controls unfocusable and named, no sideways scrolling, nothing animating. Listed absent surfaces come from US-11.11 |
| Fix round 5's small findings | PASS | R5-1 renamed. R5-2's runbook row corrected. R5-3 reads an unread count as a failed check, and `not_checked` catches a blank value, by reading, as `goal` has no test. R5-4's lone surrogate is counted, by a unit test. R5-5's text clears, by reading. R5-6's hidden picker and key handling have browser tests. R5-7's runbook line names the forms that get through |
| State what a test can't settle | PASS | The [summary](../../../docs/engineering/evidence/US-12.2/summary.md) lists each limit by row, and no paid call or persistent change was made |

Checks on the final code: `fast` and `harness` exit 0, the identity qualifier's 428 cases and the worker inference qualifier's cases pass, and `openspec validate` is clean. All new cases run in the `db` profile through `qualify_identity.py`, except the worker cases in `qualify_worker_inference.py`, which is run by hand as `python3.12 scripts/qualify_worker_inference.py`.

## Findings

- **A vacuous test of mine:** the first keyboard walk recorded 0 stops on most surfaces and passed. Found by reading its values. It now runs first, and 0 stops is a finding.
- **A real gap:** a child run had no link to its parent.

## Corrected by US-12.3's review

This record marked rows PASS that were only partly observed. Each is now either tested in US-12.3 or stated here.

- **Fix round 5's small findings:** R5-4 had neither outcome its acceptance allows, since counting the bytes let the request go on to a reservation. A request that can't be encoded now stops as `request_unencodable` before any reservation. A scripted model returning one in tool arguments was run: the run ends `failed`, with no reservation or call after it, in `tests/db/review_check.py`. A goal holding a lone surrogate is refused when `admit_run` stores it, and the API's own refusal isn't asserted.
- **Rebuild across a disconnect:** the approval assertion read an event held in the page's state, so it couldn't fail, and the duplicate check couldn't either. An approval is now decided during the drop, its event must appear, and a reload rebuilds all of it from the server. A duplicate can't render, as events are keyed by sequence, which is stated, not tested.
- **Inventory each dispatch:** the first version couldn't catch a dispatch outside the factory. Guards on name lookups and on Python's own connects now do, with a control each for a name, a loopback port and a literal address, and the tree's child is on the inventory. An SDK implicit model would show on the wire, as each request's model is compared. A connection made inside a C library wouldn't be seen, as libpq's aren't.
- **Walk each surface in both themes:** three of its checks couldn't fail. Their replacements, and a test breaking a page on purpose, are in [the summary](../../../../docs/engineering/evidence/US-12.2/summary.md).
- **Check the shape of Terra's requests:** no request sets `reasoning`, so its shape check runs only on the harness test's inputs. The allowed field list is now what's observed, and routing flags are compared exactly.
- **Return partial results across descendants:** it now reads through the run's own view, and asserts the stop reason and no tool call on the later child.
- **Use local files with no key:** the log check couldn't fail. It now asserts the run list and ledger are unchanged.
- **Inspect the goal after a compaction:** the first read now asserts no summary exists yet.
