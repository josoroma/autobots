# US-11.12 independent review, round 2

`autobots-reviewer`, in a fresh read-only context, over the tree as round 1's fixes left it. Saved as returned, in substance. Nothing was executed by the reviewer.

**Outcome: changes_required.** 3 blocking, 12 nonblocking.

## Blocking

- **R2-1.** Compaction calls still under-reserved. `_summary_route` built a route with no input rate, so a summarizer call over the assumed size reserved flat at the 32,000-token worst case, and spend could pass the run limit by the excess. WI-2 and N-new-4 stayed open on that path.
- **R2-2.** "Continue in a new run" sent `snapshot.objective`, which is cut to 500 characters and redacted, while the page said "the same goal". A long goal started a billed run on its first 500 characters.
- **R2-3.** E-2's fix stated a new falsehood. `reconciled` only meant `reconciled_at` was set. A late provider reply read as "Charge entered by the owner", and a `charge_not_reported` call that worked read as "outcome unknown".

## Nonblocking

- **R2-4.** E-9 partly resolved. An exception in the main `try`, or in the `finally` block's own `sql`, skipped `write_report()`. The after-run block caught only `Unavailable`.
- **R2-5.** N-70 partly resolved. A running job keeps dispatching paid calls for up to 30 seconds of drain, and a cut call pauses for a person.
- **R2-6.** N-71's test couldn't fail without the fix, as it never applied uvicorn's logging config.
- **R2-7.** Blocking or major fixes with no test that would fail without them: N-18, N-8, N-41, N-70, E-1, E-9, and the WI-1 and WI-2 wiring.
- **R2-8.** G-2 partly resolved. The Bash pattern named only three files under the install, `backup.key` had none, and the path rule and Bash patterns had no fixtures. `Grep` isn't a supported tool.
- **R2-9.** The lease keeper's reconnection had gaps: no beat forced on reconnect, a discount could apply twice if the connection dropped right after its commit, no cap at elapsed time, and other errors killed the keeper silently.
- **R2-10.** Continue was offered for workflow runs and children, where it doesn't continue the work. The Expert, session and input documents were dropped without saying so, and the button had no pending state.
- **R2-11.** `uvicorn.access` wasn't reconfigured, so `local-app.md`'s command kept plain access lines with full run IDs, contradicting the runbook.
- **R2-12.** New tests asserted less than they claimed: `workflow_run_check.py:213` (no reason checked), the `key_usage` network case (the new branch untested), the fake connection for `schema_behind`, `qualify_worker_inference.py:236-240` (wait ignored), `slice-run-details.spec.ts:298` (link unchecked), `test_final_review.py:62` (a real `tool_plan`).
- **R2-13.** The changed-`storage.sql` refusal and `first_setup`'s port refusal had no case, and a failed guard query produced a misleading message.
- **R2-14.** The WORKER-INFERENCE-001 record wasn't all true: a stale "No manifest yet", "confirmed the scope" where the decision says "as built", wrong statements about where live use lives, and a third round called both unreviewed and covered.
- **R2-15.** H1.3 still said DH-A01–16 pass with no exception. Other sources kept the old adapter wording. Decision 0011 overstated "a member can't reach an earlier version". `CODEBASE.md`'s revised sentence was garbled. Also noted: `narrowed_tools` silently omitted delegation where it used to refuse.

## Round-1 findings, as the reviewer read them

| ID | Verdict |
|---|---|
| G-1, E-1, N-2, N-8, N-9, N-18, N-41, WI-1, N-new-1, E-3, E-4 | Resolved |
| N-71 | Resolved in code, except access lines (R2-11) |
| E-5 | Resolved, with R2-9's limits |
| G-2, G-3, E-2, N-70, WI-2, N-new-3, N-new-4, E-9 | Partly |

Outcome line as returned: `outcome: changes_required`.
