# US-12.3 independent review, round 4

`autobots-reviewer`, in a fresh read-only context, over the fix a real sleep required in US-12.5, on the tree this record's fingerprint binds. Saved in substance. Nothing was executed by the reviewer.

**Outcome: approved.** 0 blocking, 6 nonblocking.

**Does the evidence support the cause? Yes, with a correction.** The database clock was never sampled, so its lag is a strong inference from the 26 seconds between `worker.woke` and `worker.lease_revived`, not an observation. The cap didn't clamp the discount to nothing: it reset the segment's start to the lagging now. Other causes were ruled out, including that two sleeps adding to 900 seconds was the reason, which is a coincidence.

**Every reader of a future `segment_started_at` copes.** Active time can't go negative, and no money limit is affected.

## Nonblocking

- **S-1.** Removing the cap brings back what it guarded: a clock that never catches up, a forward wall-clock step over 20 seconds, and a double discount can each leave a segment's active time uncounted. Model-call, tool and money limits still hold.
- **S-2.** A short real sleep could pass with the bug still present, as it trips only when the run hits the limit. So the proof needs a sleep of at least about 10 minutes.
- **S-3.** No case covers `end_segment` while the segment is ahead, or the keeper in the real order of beat, discount and jump.
- **S-4.** The docstring's "clamps the discount to nothing" and "showed" overstate what was seen.
- **S-5.** US-12.5's change said no source changed, and the failure lists omit `sleep_counted_as_work`.
- **S-6.** A narrow related case predates this: a segment that begins during the lag could add the whole jump to active time.

Outcome line as returned: `outcome: approved`
