# US-1.1 — H0 repository and prerequisite inventory

## Plan

Source: [US-1.1](../../../SPECS.md#us-11-h0-repository-and-prerequisite-inventory), SP-001 item 1, DH-02 H0.1, SP-020 H0-01, [DH-W01–06](../../../PRD-Development-Harness.md#dh-091-work-item-evidence-contract). Delivered through `/ohmyorch:deliver EPIC-1`, change `us-1-1-h0-repository-prerequisite-inventory`. This is the first story through the loop, so it also qualifies the loop.

**Intended behavior:** a versioned inventory at `docs/engineering/prerequisite-inventory.md` records actual paths, versions and missing prerequisites without secret values, and evaluates item by item whether version control or a required ignore is absent. Version-control and ignore configuration change only where something is missing.

**Invariants:** no secret value recorded or read; no unrelated setting overwritten; no install, service start or model call; no compatibility verdict, which is US-1.3; presence is not reported as qualification.

**Affected layers:** documentation and `.gitignore`. No contract, state or migration changes. Full scope, order and verification are in the change's `implementation-plan.md`.

**Decisions by the user, 2026-11-04.** The first three are recorded in Decision 0002. The last two are recorded here and go into Decision 0002 at US-1.2 `select`:
- Local transcripts are recorded as not missing, with no rule added. This rests only on the decision: the samples exit 1.
- Five cache rules are added in this story (`.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo`, `.pnpm-store/`). Those five close the cache question for US-1.1, and later stories add ignores for tools they introduce. Other caches also have no rule and are not claimed as covered.
- Protected paths are authored by the implementer and written verbatim by the coordinator.
- A Given such as "required ignores are absent" holds if any required item is absent, and a decision that one item is not required removes only that item. Confirmed by the user for all stories. US-1.1's hygiene PASS relies on this reading; it originated in review F-6.
- `research/qwen38-gguf-probe.json` and `research/qwen38-gguf-performance.json` are historical experiment evidence, not DH-03 local transcripts. They stay tracked. Their message text was not read. The proposal's "nothing forbidden was found committed" predates this finding and did not see them; this ruling decides it.

**Decisions by the coordinator:** the inventory path; meeting DH-W05 by reference to the existing harness runbook; finding dispositions below; the wording of F-9's replacement sentence.

**Rollback:** remove the inventory and the five rules, restore the status in `SPECS.md`, and revert the story commit.

## Implementation

Author: `ohmyorch:implementer`, a separate delegated context, across two rounds.

**Changed by the implementer:** `docs/engineering/prerequisite-inventory.md` (new) and `tasks.md` in the change (16/16 ticked, R1.7 to R1.9 by the coordinator; R1.9's replacement wording was not itself put to the user, see F-12). Ignored output went to `.checks/US-1.1/`.

**Persisted through the protected-path procedure:** `.gitignore`, five lines after the managed block. The implementer authored and pre-tested them, the coordinator wrote them verbatim with the Edit tool (SHA-256 of the lines `bc0aea2e…287c` matches the implementer's copy), and the implementer then probed the real file.

**Coordinator changes in this story:** `SPECS.md` status and `Change:` line; `CODEBASE.md` revision, its note and a pointer to the inventory; `.claude/rules/ohmyorch-delivery.md` and Decision 0002, recording decisions made while delivering, and fixing R1.7 to R1.9; the proposal, plan and spec delta as the planner authored them, and the OpenSpec-generated `.openspec.yaml`.

**Actual behavior:** the inventory records 159 tracked files at base `34ae38f`, assets, every install path found on this shell's search path with versions, and `pnpm` as missing. Version control and the other ignore rules predate this story. This story established the five cache rules only.

**Deviations reported by the implementer:**
- First round: sections written in one pass and then verified, not task by task. Tasks 1.4 and 2.3 still ran last on the final text.
- Probes beyond the plan, none reading a secret-bearing file: `which -a docker-compose`, `ls -l` on tool links, `ls ~/.nvm/versions/node/`, `head -1` on Node script tools, `/usr/bin/env` version checks, `test -e .claude/settings.local.json`, an `ls .claude`, a grep of `.claude/settings.json` for hook commands, and field names only from two `research/` files.
- `supabase --version` wrote an update notice naming v3.0.0 to stderr, which appears to be an outbound check, so several rounds repeated it.
- A search of `PRD-Model-Providers.md` printed the provider master-key file's name into its tool output. The file was not touched, and the name is not in the inventory.
- An OhMyOrch guard refused one helper-script write outside the project. It was not retried, and the comparison ran through Python on stdin instead.
- Second round: R1.2 to R1.6 were ticked before the task 2.3 commands ran, which then passed; three label rows instead of one for R1.4; two inventory sections beyond those listed.

**Findings beyond the plan, not acted on:** a second Python 3.12 at `~/.local/bin` (3.12.9); npm and Corepack have several installs; OpenSpec, npm and Corepack start through `/usr/bin/env node`, which resolves to Node 26 here although OpenSpec is installed under nvm v22; scripts' `#!/usr/bin/env python3` resolves to 3.15.2, so only the documented `python3.12` commands were run under 3.12; `PRD-Development-Harness.md` writes `python3 scripts/verify.py` where `AGENTS.md` uses `python3.12`; `check-scope` without `--diff` reports no changes on a dirty tree.

## Review

**Reviewed fingerprint (final):** `09b978de1c9eaa4bb57629ff84b058a57a9b9f4ee58002fbbbfa86238a72de2c`, 11 files. Verdicts at their archived path: [review.md](../../../openspec/changes/archive/2026-11-04-us-1-1-h0-repository-prerequisite-inventory/review.md), [test-report.md](../../../openspec/changes/archive/2026-11-04-us-1-1-h0-repository-prerequisite-inventory/test-report.md) and `history/` beside them.

| Round | Reviewer | Result |
|---|---|---|
| 0 | `ohmyorch:reviewer`, fingerprint `69df0ac2…dbb8` | First `pass` 1/2 with F-1 to F-5, then reissued as `changes-requested` once the cache gap was decided, with blocking F-6 and F-1 to F-9. The first text was overwritten and not preserved as a file; `history/review-r1.md` is the reissue |
| 1 | `ohmyorch:reviewer`, a fresh context | `pass`, 0 blocking, 2/2 criteria. See `review.md` |
| 1, adversarial | Three read-only lenses over both verdicts | 7 non-blocking refutations. No conclusion changed, but some recorded details were wrong and are listed below. The 7 are: the `risk-policy` quote, the role-object counts, the pending-file scan and the raw-output location (the last two each raised twice), and F-12 |
| 1, evidence | `autobots-reviewer`, over this record and the summary | First pass: 6 blocking findings, E-1 to E-6, all in these records. See below |

| Finding | Disposition |
|---|---|
| F-6, blocking: cache rules absent | Fixed by user decision; rules added and probed |
| F-1 to F-3, F-7, F-8: inventory accuracy | Fixed by the implementer |
| F-4, F-5, F-9: bridge rule and Decision 0002 wording | Fixed by the coordinator. F-9's replacement sentence is the coordinator's wording, see F-12 |
| F-10, medium: this record still stated round-0 outcomes | Fixed by this rewrite |
| F-11, low: Decision 0002 says all decisions are in the bridge rule; "only when named" and "all epics" do not say how they relate | **Carried to US-1.2 `select`**. The user's words were "loop delivery one epic by epic until complete all". The coordinator reads that as naming every epic |
| F-12, low: R1.9 is ticked, but its replacement wording was not put to the user, and bridge line 71 presents the coordinator's reading under "decided by the user" | The "any required item" sentence was then **confirmed by the user** for all stories; US-1.1's PASS relies on it. The "disposable environment" sentence was **not** put to the user: no story has used the exception, and the sentence stays the coordinator's wording. **Carried to US-1.2 `select`:** separate the two in the bridge rule |
| F-13, low: inventory says install paths come from `which -a`, but the Compose plugin path did not | Accepted. The value is correct, and fixing it would need a new capture and review |
| Adversarial: `risk-policy` quoted in `review.md` and `test-report.md` is not in `SPECS.md`; the real hit is `task-policy` at line 57 | Accepted. No secret is present, and the false-positive conclusion holds. The evidence records the correction |
| Adversarial: `test-report.md` line 292 counts of role objects cover only user and assistant roles | Accepted. Evidence records the structural count; message text was not read. The tester's question on these files went to the user; see Decisions |
| Adversarial: the tester's pending-file scans covered 16 of 19 files, omitting verdict and history files | Accepted. The three omitted were `test-report.md` and the two history files; `review.md` was scanned. The checkers scanned them: no secret, only quoted regexes and the `sk-` false positive |
| Adversarial: `.checks/US-1.1/tester/r2/` lacks raw output for several probes and for the fixture | Accepted. Those results exist only as text in `test-report.md`, including the DH-W05 results for `specs.py validate` and the `not_implemented` runs, and the evidence says so |
| E-1 to E-6: overstated or missing statements in this record and the summary | Fixed here and in the summary, and re-checked by the same reviewer. E-2's and E-4's questions went to the user |
| E-7: the re-check found this record claimed two rulings were already in Decision 0002 | Fixed in the Decisions heading. That one-clause fix and the re-check's non-blocking wording fixes were not re-reviewed |

**Carried forward, durable note in `openspec/delivery/goal.md`:** at US-1.2 `select`, update Decision 0002 and the bridge rule with F-11, F-12 and the two rulings above, and US-1.2's plan names those paths.

## Verification

See the [evidence summary](../evidence/US-1.1/summary.md). Harness results are harness evidence only.

## Runbook

Operating behavior is unchanged. [Development harness runbook](../runbooks/development-harness.md) applies, with `python3.12 scripts/verify.py --profile harness` as its regression check. The tester exercised its "Run the delivered checks" procedure; the results are in the test report and the evidence summary.
