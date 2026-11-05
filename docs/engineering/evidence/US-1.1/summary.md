# US-1.1 evidence

**Scope:** the repository and prerequisite inventory, and five cache ignore rules. Requirements: SP-001 item 1, DH-02 H0.1, DH-03, SP-020 H0-01. This does not establish H0, H1 or product acceptance. It is also the first story through the OhMyOrch loop. [Work record](../../work-items/US-1.1.md). Change: `us-1-1-h0-repository-prerequisite-inventory`.

**Evidence kind:** static and local probes, plus a disposable fixture of two scratch Git repositories, run by the tester. No mock, service, database or model call. `supabase --version` appears to make an outbound update check (inferred from behavior, not captured).

## Reviewed inputs

`reviewed-manifest.json`: 11 files, fingerprint `09b978de1c9eaa4bb57629ff84b058a57a9b9f4ee58002fbbbfa86238a72de2c`. `review.md`, `test-report.md` and the manifest state the same value. `test-report.md` records `story_manifest.py compare` passing first and last. The reviewer reported the same in its handback; `review.md` does not record it.

## Scenario results

| Scenario | Result | Basis |
|---|---|---|
| Preserve existing work | PASS, by `ohmyorch:tester` | 24 tool versions, 19 asset paths and 159 tracked files re-run and matching; `pnpm` missing as recorded; secret-shape scan clean; tracked settings unchanged |
| Establish repository hygiene | PASS, by `ohmyorch:tester` | The Given held: base has 0 of the five rules. All 6 cache samples exit 0 against the real file, and `-v` names `.gitignore` lines 25–29. Lines 1–24 match base. The tester's fixture staged real files under both `.gitignore` versions: base staged the five cache categories, the current file did not, and the lists otherwise matched |

**What rests on a decision, not a probe:** local transcripts are "not missing" by the user's decision only, and 3 samples exit 1. The five rules closing the cache question is also a user decision: 7 other cache samples exit 1, and no record claims every cache is covered. The PASS relies on the reading that a Given of this shape holds if any required item is absent, which review raised and the user confirmed.

**Tracked research payloads:** the tester found that `research/qwen38-gguf-probe.json` and `research/qwen38-gguf-performance.json` hold model request and response payloads, and that no name scan surfaces them. The user ruled them historical experiment evidence, not local transcripts, and they stay tracked. The tester states it did not read their message text, and the checkers report counting keys and role values only, so their content is not characterized here.

**What this story did not establish:** version control, and the other ignore rules, which predate it. The hygiene "without committing" clause was assessed before the story commit existed, on name and content scans of pending files, which do not prove absence.

## Runbook

DH-W05 met by reference to the [development harness runbook](../../runbooks/development-harness.md). The tester exercised "Run the delivered checks": `specs.py validate` exit 0; `verify.py --profile harness` exit 0 with 69 tests; `--profile db`, `fast`, `full` and `operations` each exit 2 with `not_implemented`. It set `TMPDIR` and `PYTHONDONTWRITEBYTECODE`, so the default temporary location was not exercised. **Untested:** `render` by the tester, the whole "Inspect or use the assistant integration" section, and the failure and recovery table.

## Corrections to the verdicts

Found by adversarial checks, which edit nothing. The verdicts stand as written.
- `review.md` and `test-report.md` quote `risk-policy` as the false-positive secret-shape hit. That string is not in `SPECS.md`. The hit is `task-policy` in a navigation anchor at line 57: `sk-` matched inside it. No secret is present.
- `test-report.md` line 292's role-object counts (58 and 5) cover user and assistant roles. A structural count, reading keys and role values only, gives 85 and 6.
- The tester's pending-file scans covered 16 of 19 files. The three omitted were `test-report.md` and the two history files. The checkers scanned them: no secret, only quoted regexes and the `sk-` false positive above.
- `.checks/US-1.1/tester/r2/` holds only tool versions, Supabase stderr, `pending-files`, `latest-before` and `verify-harness` output. The ignore probes, scans, fixture, repository and asset probes, `specs.py validate` and the four `not_implemented` runs exist only as text in `test-report.md`, and the fixture was removed.

## Loop qualification from this story

This is coordinator observation from this session, not event-delivery qualification: `.claude/autobots.json` still records that as not qualified, and neither verdict covers it.

- Carried from setup, not this story: the plugin's `PreToolUse` hook refused a main-session verdict write (HARNESS-OHMYORCH-001).
- `ohmyorch:planner`, `implementer`, `reviewer` and `tester` ran as delegated agents, and the reviewer and tester each wrote their verdict file, including from inside a workflow. No identity artifact was retained.
- Beyond their verdict files, the reviewer and tester disclosed other writes: both refreshed `.checks/harness/latest.json`, and the tester wrote `.checks/US-1.1/tester/` and fixture output. Shell writes bypass the guards, so scope is by disclosure and inspection, not mechanically shown.
- The implementer reported that a guard refused one write outside the project; the refusal itself was not observed by anyone else.
- `delivery reopen` preserved the verdict files under `history/` and appended remediation tasks. `delivery stop` and `start` resumed from repository state, as the coordinator saw in command output.

`completion-gate --record`, `openspec archive` and `mark-done` then ran as the bridge orders them, and `promote` moved US-1.2 and US-1.3 to `READY`. The [final manifest](verification.json) has the final harness fingerprint and input manifest.

**Friction for later stories:**
- Waiting on background agents inside a turn needs a foreground wait, because ended turns count as stalled stops.
- Protected-path files need two implementer passes.
- The project hook's 20,000-character shell limit requires larger coordinator edits to go through a file.
- A reissued verdict overwrites the earlier text before `reopen` preserves it.

## Limits

User decisions are known to specialists only from project records. Non-overwrite of `.claude/settings.local.json` is supported only by its modification time. Secrets outside the scanned shapes are not excluded. Real cache tools were not run; rules are shown on sample paths. Later plugin upgrades leaving the appended `.gitignore` lines alone was read in code, not exercised. Also from the verdicts: the review does not claim archive readiness; Design Adherence is not verified, because `design.md` is intentionally absent; OpenSpec verification steps were followed by hand; installs outside this shell's search path, such as a Corepack under `~/.hermes/node/bin`, are not in the inventory; the master-key filename had no mechanical check this round; home-directory caches and telemetry were not observed; one tester command batch was denied once by Claude Code for `rm -rf` on a variable path and re-run without it; and the plan and runbook differ on `--profile db`, which the tester ran as a checked limitation.

## Archive conditions

Before `archive`: `python3.12 scripts/story_manifest.py compare US-1.1` printed `PASS: compare: US-1.1: 11 files match the reviewed manifest`, exit 0. `verify.py --profile harness` exit 0 (harness evidence only). `test-report.md` has no `UNVERIFIED` row.
