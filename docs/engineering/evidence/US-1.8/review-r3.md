# US-1.8 independent review, round 3

Persisted verbatim from the reviewer's final message. Corrections it asked for are listed in [summary.md](summary.md).

**Reviewer:** same separate read-only context; independent of the author, not fresh. I executed nothing.

**Outcome: approved** for the portable baseline. Nothing blocks Gate 0. This doesn't close DH-A03's Claude part, event delivery, the persistent stack or product acceptance.

**Round 2 items:** N-1 is resolved (`evidence.py:230-231`, test `:220`). N-3 and N-5 are resolved, and N-2 and N-4 match their stated dispositions. The summary's dispositions match my findings, except that `.env*` is broader than stated (below).

**Records:** all final reports share fingerprint `0bc24da6…`, are stable and passed, with 190 tests executed and 0 skipped. Fault (21/21) and disposable case results match the summary. Glob's modification-time order places the runs after the last source edit; that is my inference.

**Correct before `complete`.** These are record-only, so no re-review is needed if limited to them:
1. `summary.md:12`: "under `env -i`" and "With tools missing, exit 2" have no retained final-input artifact. Retain them, or cite the fixture level and US-1.4.
2. `summary.md:20`: no check asserts "No secret in reports". My pattern search of reports and artifacts found none, but it can't recognize raw generated values. State that limit.
3. `summary.md:36-45`: recovery commands are missing from Reproduction. `exercise.sh` and `committed_fault.sh` are unhashed and outside `local_root`; copy them in and hash them (DH-A16).
4. `gate-0.json:914-915,945-946`: manual times are dates only, not UTC start and end (DH-09.2). Disclose or fix.

**Nonblocking, disclose**
- R-1: `evidence.py:169-170` accepts `exercises_runbook` on a report-cited check. A hand-added fake artifact with `availability: deleted` passes. Restrict it to manual checks later.
- `harness_lib.py:117` excludes every `.env*` name, such as `.environment.py`, not only `.envrc`.

**Binding:** accepted, for `source_manifest_sha256` `6df279da…` only if `fingerprints` still prints it and `validate` exits 0. Any change to a non-record input voids approval. The source hash excludes runbooks, so a runbook edit needs its own re-record and re-exercise. I cannot confirm the hash covers what I read.

**Disclosed limits:** the three from round 2 are acceptable. Others: manual results are author assertions, versions are read at record time, fixtures are synthetic, and most of `tests/toolchain` runs in no profile. This round I read changed regions, not every file in full. The lockout account is unverifiable by me.
