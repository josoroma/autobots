# US-12.4: the two-call workload

**Class: live, on disposable stacks.** Real OpenRouter calls on Terra, through the product's API and two `worker.main` processes. Rounds 1 to 4 ran at US-12.3's first binding, source fingerprint `09ea61fb…`. US-12.5's fix voided it, so round 5 ran at the binding that replaced it, `05916d5e…`. This doesn't establish H1 or product acceptance, a persistent stack, or responsiveness under load.

**Result: not cleanly stable.** Four rounds were stable. In the first, one goal's first call paused as `uncertain_acceptance`, and I never found why. Nine of ten goals succeeded and passed verification. LM-A09 stays partial, and the owner is told.

## What ran

Two goals at once, each with a required artifact, in one workspace. The story asked for one run. The first run's pause had no recorded cause, so I ran three more to catch one, under the same cap, and none recurred. Round 5 repeats it at the rebound fingerprint.

| Round | Result | Goals | Calls | Calls overlapped for | Workload | Reported charges |
|---|---|---|---|---|---|---|
| 1 | **Failed: a run paused** | `succeeded` and `paused` | 6 | 1.3 s | Stopped waiting at 600 s | US$0.005415 |
| 2 | Stable | both `succeeded` | 11 | 10.5 s | 18.8 s | US$0.011215 |
| 3 | Stable | both `succeeded` | 12 | 14.9 s | 23.4 s | US$0.011997 |
| 4 | Stable | both `succeeded` | 11 | 13.7 s | 18.4 s | US$0.011638 |
| 5, after US-12.5's fix | Stable | both `succeeded` | 11 | 12.0 s | 18.5 s | US$0.011363 |

Each round's samples are in `round-N.json`. Rounds 2 to 5 ran `logging_worker.py`, which is the product's worker with one logging wrapper added, so they aren't quite the product's entry point. Round 1 ran the product's.

## The failed round

- **What happened:** the run's first call ended after 1.3 seconds, and the run paused with `uncertain_acceptance`, holding its reservation. Nothing crashed, no status was false, and no worker step failed. The run did what the product says it does with a call that may have been charged.
- **It probably wasn't charged:** key usage rose by US$0.005416 in that round, against US$0.005415 for the other run's reported charges. So that call seems to have cost nothing, and may never have been sent. This rests on one reading 60 seconds later.
- **The cause is unknown.** The product records only the class, and anything without a status counts as uncertain. It could be the SDK refusing a reply, as WI-7 feared, or something before sending. Four more rounds with the exception logged didn't reproduce it.
- **What it means for a person:** a run can pause asking them to look up a charge that may not exist, with nothing saying why. That's safe with money and costly in attention. Recording the exception's type would need a source change, which would void US-12.3's binding, so it's left for the owner.

## Resources

Peaks, sampled every few seconds, across rounds 1 to 4, and round 5 is close to them. Docker's peak there was 23.9% and 808.5 MiB. Rounds 2 to 5 have only 4 or 5 samples each, as their workloads were short, so these are coarse.

| | Peak CPU | Peak memory | Peak TCP connections |
|---|---|---|---|
| UI | 9.6% | 116 MB | 1 |
| API | 7.3% | 171 MB | 3 |
| Each worker | 22.2% | 170 MB | 8 |
| Docker, 8 containers | 23.4% | 808 MiB | 22 database connections |

Disk used grew by 18 to 34 MB across a round, and the database by 400 to 480 KB. The disk figure is the whole volume, so other activity on this Mac is in it. No service went unhealthy, and the API and UI answered at every sample.

## Spending

| | |
|---|---|
| Reported charges, five rounds | US$0.051628 |
| Key usage | `0.864570985` to `0.916198135`, a rise of US$0.051627 |
| Shared ledger, after round 5 | **US$0.309802 of US$1** |

The ledger is higher than what was spent because it still holds round 1's whole US$0.25 budget: a run that isn't finished could spend again on resume, by the rule the install goal follows. That stack has since been removed, so it can't, and nothing was released by hand. Rounds 2 to 5 used a US$0.10 limit each, to leave room for US-12.6.

The key is in no durable row or log, by the runner's scan, which covers the OpenRouter key only. Other Docker resources were unchanged, and no stack was left behind.

## The cap

On an arranged ledger 10 micro-USD below the cap, the runner refuses before any stack or request, reports nothing sent, and leaves the ledger as it was. The real ledger hasn't come near the cap.

## Limits

- **A short workload.** Goals of about 15 seconds, so this says little about long runs at two calls, resources over time, or anything like load.
- **Rehearsed first:** on a fake transport, both workers finished two goals with calls overlapping for 0.2 seconds. That shows the arrangement, not stability.
- **Which worker took which run isn't recorded,** as a job's owner clears when it finishes. Overlapping calls from different runs show both were working.
- **Responsiveness under load wasn't measured,** as Decision 0013 named resources only.

## Reproduction

```sh
PYTHONPATH=services/agent/src services/agent/.venv/bin/python docs/engineering/evidence/US-12.4/measure_two_calls.py --rehearse
PYTHONPATH=services/agent/src services/agent/.venv/bin/python docs/engineering/evidence/US-12.4/measure_two_calls.py --paid
```

The second spends money. Both scripts are kept here, as a file under `scripts/` would void US-12.3's binding.
