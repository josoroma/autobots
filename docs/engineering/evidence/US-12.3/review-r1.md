# US-12.3 independent review, round 1

`autobots-reviewer`, in a separate read-only context, over everything since `5135601`. Saved in substance. Nothing was executed by the reviewer.

**Outcome: changes_required.** 5 blocking, 15 nonblocking. It also found no path that starts new work on DeepSeek, by reading every caller of `admit_run`.

## Blocking

| ID | Finding | What was done |
|---|---|---|
| F-1 | The run disclosure stated a route the server would refuse, on Home, a session, Continue and the workflow editor | It says the run would start nothing, by the server's own rule, and a test holds it |
| F-2 | R5-4 was PASS with neither outcome its acceptance allows | `request_unencodable`, before any reservation, and a goal with a lone surrogate is refused on the way in |
| F-3 | The LC-25 inventory couldn't catch a dispatch outside the factory, and left out the child | A guard below the factory, with a control, and the tree on the inventory |
| F-4 | Three of the walk's checks couldn't detect their own failure | Replaced, with a test that breaks a page on purpose |
| F-5 | The approval half of "Rebuild across a disconnect" was retained state | An approval decided during the drop, then a reload |

## Nonblocking, all fixed unless stated

F-6 the compaction's "before" read. F-7 a no-key log check that couldn't fail. F-8 LC-04 narrower than its text. F-9 `REQUEST_FIELDS` too generous. F-10 test titles and assertions. F-11 the banner reading the draft. F-12 the Expert editor dropping the reason, and bindings it doesn't show. F-13 the composer checking 422 first. F-14 `/v1/runs/intent` saying ready. F-15 a workflow with no agent step refused. F-16 the picker returning. F-17 the failure report's labels. F-18 US-12.1's record, corrected in place. F-19 requirement text. F-20 `live_goal.py`'s option.

Outcome line as returned: `outcome: changes_required`
