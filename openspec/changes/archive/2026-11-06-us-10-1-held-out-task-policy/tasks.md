## 1. The held-out result (scenario: Measure the scoped release corpus)

- [x] 1.1 Confirm the corpus's hash is unchanged and no prompt or goal-loop code changed since the run, checked by `git diff` against the run's commit
- [x] 1.2 Record the user's decisions on the plan-rejection margin and the assistant-written corpus in a decision record, checked by reading it against the evidence

## 2. Measuring what's missing (scenario: Measure local responsiveness separately)

- [x] 2.1 Require an explicit spending cap, and sample CPU, memory, disk, connections and UI/API availability while goals run, with the summary checked by `tests/harness/test_release_qualification.py`
- [x] 2.2 Read a killed worker's lease expiry, and report recovery from it, checked by the same run's report
- [x] 2.3 Add `release-latency.spec.ts`, which times a committed event until the real UI shows it, checked by the paid run
- [x] 2.4 Run it once on `dev_tasks.json` under the US$1 cap, and keep the raw report in `.checks/release-resources`

## 3. Publishing (both scenarios)

- [x] 3.1 Publish the measurements, costs and limits in `docs/engineering/evidence/US-10.1/summary.md`, and correct `CODEBASE.md`, checked by reading them against the raw reports
