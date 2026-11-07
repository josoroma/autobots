# US-12.8 review, round 1

`autobots-reviewer`, in a separate read-only context that didn't write the change. It read everything since `70c5162`, and the release record that [`review-r3.md`](../US-10.2/review-r3.md) left unread. It ran nothing.

**Outcome: changes_required.** 4 blocking, 7 nonblocking. It found no defect in the product code. Each answer on one event per path, no message text, and logging not changing a failure, came from reading the code.

## Blocking

| ID | Finding | What was done |
|---|---|---|
| RG-1 | The record's cancellation row said nothing stayed reserved, from a check on `public.runs.reserved_micro_usd`, a column nothing writes, so it couldn't fail | The runner now reads the product's own ledger figure, and fails if nothing is held. It showed 34,560 micro-USD held on all 12 runs, so the row now says the interrupted call's reservation stays until reconciled |
| RG-2 | "Final tree" for measurements at an earlier fingerprint, on DS-05 and B7 | Reworded |
| RG-3 | The verdict omitted SP-021's generated contract consistency and SP-019's scenarios | A section and table added |
| RG-4 | DS-03 "pass by absence" contradicted the verdict | Its row cites the sources and says it's this record's reading, and the verdict says so |

## Nonblocking

| ID | Finding | What was done |
|---|---|---|
| RG-5 | PRD 13.1's stability target is neither met nor revised | The row says so, and Decision 0014 records it |
| RG-6 | Behaviors with no failing test | Tests added, and round 2 found more |
| RG-7 | `[dropped]` asserted little, and \"mid-reply\" overstated it | Asserts type, request count and ledger. Named before a reply |
| RG-8 | \"Reaches the exception's message\" wasn't shown, and request text wasn't checked | Corrected on US-12.7's record, and a goal's text is now checked |
| RG-9 | The runbook row was loose | It names the file and the cancelled case |
| RG-10 | Older requirement text wasn't covered | Decision 0014 records it |
| RG-11 | Small limit and citation gaps | Fixed |

## What it told the coordinator to say

The owner chose \"stores the exception's type\". A log is within those words and disclosed in Decision 0014, but the choice between a log and a screen was the session's, so the owner should be told plainly.
