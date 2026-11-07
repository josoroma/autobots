# US-12.8 review, round 2

`autobots-reviewer`, in a fresh read-only context. It checked round 1's fixes by reading them, and ran nothing.

**Outcome: changes_required.** 4 blocking, 6 nonblocking.

## Blocking

| ID | Finding | What was done |
|---|---|---|
| RH-1 | No check failed if the guard at the first call site went, so a key removed mid-run could log an uncertain event for a call never sent | `verification_check.py` runs a known failure from inside the call, and asserts no new event |
| RH-2 | Reading only `__context__` still passed | A test with a cause and no context |
| RH-3 | Decision 0014 called a mapped document unmapped, and two lines weren't attributed | Corrected, and attributed to the delivery session |
| RH-4 | DS-05 and DS-04 name the same undelivered surfaces as DS-03, and the verdict named only DS-03 | Rows and verdict widened |

## Nonblocking

| ID | Finding | What was done |
|---|---|---|
| RH-5 | SP-019 table gaps | LC-34 added, and SP-010 and SP-014 stated |
| RH-6 | \"SP-020 defers a complete canvas\" overstated it, and stronger sources were missed | Replaced, and the owner is pointed at Decision 0009's B7 |
| RH-7 | The verdict omitted the target marked not met | Stated |
| RH-8 | The `str()` claim was imprecise | Reworded |
| RH-9 | A status assertion tested nothing about its guard | Runs through the real loop now |
| RH-10 | A stale count in the Gate 0 plan | Refreshed |
