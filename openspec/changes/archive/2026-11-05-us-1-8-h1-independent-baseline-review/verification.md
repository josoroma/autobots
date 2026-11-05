# Verification — us-1-8-h1-independent-baseline-review

Change: us-1-8-h1-independent-baseline-review
OpenSpec verify: VERIFIED by the main session, with the limits below. An independent review did run, because this story's acceptance requires it.
Verified: 2026-11-05

Base revision `b94727d`, working tree with this change. Full results: [the Gate 0 summary](../../../docs/engineering/evidence/US-1.8/summary.md) and manifest, bound to `source_manifest_sha256` `6df279da…`. No model call. Disposable Docker projects only, all removed.

## Scenarios

**Close Gate 0 honestly: observed, with one gate partial.**
- **Independent review:** `autobots-reviewer`, a separate read-only context, ran three rounds: 6 blocking and 8 nonblocking findings, then 1 new blocker and 4 others, then approved. It executed nothing. The same context ran all three, so it was not fresh.
- **Required findings resolved:** F-1 to F-6 and N-1, covered by fixtures. F-5 and F-6 were also observed on real runs: a committed type fault fails `fast` with a clean Git tree, and a skipped test fails `harness`.
- **Runbook exercised, including failure and recovery:** a stale `verify.lock` gives exit 2 and recovers after confirming the PID is dead. A killed qualification left 1 container and 1 volume, and `cleanup` removed them.
- **Current evidence:** on final inputs `harness`, `fast`, `full` and `db` exit 0, with 190 harness tests executed and 0 skipped, 21 of 21 fault cases and 44 of 44 disposable cases. `scripts/evidence.py complete US-1.8` passed.
- **Partial:** DH-A03's Claude crash, timeout and Stop recursion behavior is not qualified. The summary states this, and does not count it as passed.

**Report optional adapter status: observed, with the incompatible state arranged.** The real client meets the minimum version, so this Given does not hold naturally. With a stub reporting 2.1.200, `harness` exits 0 and the adapter is `inactive`, `version_below_minimum`. With no client on `PATH`: `inactive`, `unavailable`. On the real client: `configured_unqualified`, `delivery_unverified`, never active. `not_tested` lists Claude event delivery in each report, and the summary does not claim fixtures as delivery.

## Findings

- **Review caught real defects that this session's own verification had missed:** evidence could certify unstable or hand-written results, `fast` passed with committed broken code, and skipped tests counted as passes. Those stories' `verification.md` files recorded VERIFIED before this. They describe behavior as it was then, and these fixes change it.
- **Self-inflicted lockout:** a regex quoting error broke the dispatcher, whose fail-closed hook then blocked all my file and shell tools. I asked, and the user approved one terminal command to repair it.
- **Open and disclosed:** R-1, the `.env*` exclusion, `Grep` outside the hook matcher, `.checks` being hand-editable, synthetic fixtures, and most of `tests/toolchain` being in no profile.
- **Review binding:** the approval holds only while `fingerprints` still prints `6df279da…` and `validate` exits 0. Any later source change voids it, including the next story's. That is expected: the record describes this baseline.
- **Not established:** H1 as a full claim, because of DH-A03's Claude part; the persistent stack; product acceptance; live inference.
