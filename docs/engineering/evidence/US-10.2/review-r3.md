# Independent read of the release record, third version

`autobots-reviewer`, in a separate read-only context that didn't write the record. It read the first draft of the third version against the PRDs, decisions, stories and evidence, and ran nothing.

**Outcome: changes_required.** 6 blocking, 13 nonblocking. It found "met, with its stated limits" supported for H1, apart from RF-4. The record was then corrected for all of them, and the corrected version wasn't read again. The review that a new binding needs would read it.

## Blocking

| ID | Finding | What was done |
|---|---|---|
| RF-1 | LC-18 wasn't partial, though prompts sent and stored objects were never scanned | Scanned, on a disposable stack, in [`closing-checks.json`](closing-checks.json), with a control |
| RF-2 | LM-A04 wasn't partial, though LM-07 names a Docker restart | Partial, and item 4 for the owner |
| RF-3 | The record said US-10.1's targets were met, where cancellation was measured on queued runs only, and PRD 13.1 had no row | Measured on running runs, in the same report, and PRD 13.1 has its own table |
| RF-4 | The record implied accepting an item is free, though decisions and PRDs are fingerprint inputs | Stated on the H1 line and under the owner's items |
| RF-5 | LC-13 was accepted by no decision, as a test can arrange a cut | Arranged, by TCP reset, in the same report |
| RF-6 | Uncounted active time was a limit that no decision accepts | Item 5 for the owner |

## Nonblocking

| ID | Finding | What was done |
|---|---|---|
| RF-7 | LC-25 omitted F3-2 and Unix sockets, and didn't say why it differs from LC-03 | Stated |
| RF-8 | Only round 1, the one that paused, ran the product's entry point | Stated in item 1 and Revisions |
| RF-9 | MP-A09's wording implied the cap held under contention live | Reworded |
| RF-10 | LC-20, MP-A12 and LM-A06 didn't cite WORKER-INFERENCE-001 | Cited |
| RF-11 | LC-31 and LM-A08 blurred what ran on the install, and item 2 omitted a real provider across a sleep | Stated |
| RF-12 | DS-03, DS-04 and DS-05 omitted limits, and `walk.json` is older than the rebind | Stated, and `US-11.11/results.json` cited |
| RF-13 | The H1 line didn't say how Decision 0003's clause is met, or name US-1.1, US-1.2 or the review chain | Stated, and on DH-A13 for the work item's base |
| RF-14 | LC-23 attributed the `tool_required` miss to what Decision 0013 accepted | Separated |
| RF-15 | "Never exercised" holds only live, and arranging selectors can't work | Corrected in MP-A07 and item 3 |
| RF-16 | "The same fingerprint" rests on the author's statement for US-12.5 and US-12.6 | Caveat added |
| RF-17 | US-12.3's and US-12.4's verification files are stale | The legend points to their summaries |
| RF-18 | N-70, the reload's second paid run and US-10.1's age had no owner decision | Item 6 for the owner |
| RF-19 | Wording: Terra's goals, classes missing from the legend, N-48's skill text | Fixed |

## Its limits

It didn't read most records for US-2.x to US-9.x or most test bodies, couldn't compute hashes or read commit trees, and didn't assess code quality. `evidence.py validate US-12.3` then ran and passed, at source fingerprint `05916d5e…`.
