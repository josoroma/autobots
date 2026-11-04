# HARNESS-OHMYORCH-001 evidence

**Scope:** setup of the OhMyOrch epic delivery loop. No `US-*` story was delivered, no story status changed, and no application, database, service or model call was involved. This does not establish H0, H1 or product acceptance, and it does not prove the loop works end to end live. [Work record](../../work-items/HARNESS-OHMYORCH-001.md).

## Environment

Python 3.12.16, OpenSpec 1.13.2, jq 1.7.1, Bash 3.2.57, Claude Code 2.1.314. Plugin 0.0.1 at commit `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`; `installed_plugins.json` records the same `gitCommitSha`, and `diff -r` shows no difference between the cached copy and the checkout's plugin directory.

## Repository checks

| Command | Exit | Observed |
|---|---|---|
| `python3.12 scripts/verify.py --profile harness` | 0 | `project_configuration`, `backlog_validation` and `harness_behavior_tests` passed. Test count and fingerprint: see [the manifest](verification.json) |
| `python3.12 scripts/specs.py validate` | 0 | 10 epics, 42 stories, 86 tasks |
| `python3.12 scripts/specs.py promote`, on the real backlog | 0 | `no story eligible`; `SPECS.md` unchanged |
| `ohmyorch doctor --json` | 0 | Enabled, no non-PASS check |
| `ohmyorch validate-product-artifacts` | 0 | 0 failures, 2 advisory warnings |
| `git diff --stat -- SPECS.md` | 0 | No change |
| `git diff -- PRD-LangChain-Deep-Agents.md` | 0 | 2 insertions: the `CODEBASE Context` line and a blank line |

Author's report, with no retained artifact: the new tests were run before their fixes and failed for the fingerprint exclusion and for dependency prose. `story_manifest.py` tests were written together with the script, so they did not fail first.

## Live observation

In this session, a main-session `Write` to `openspec/changes/live-hook-probe/review.md` was refused by `.../research/upstream/OhMyOrch/plugins/ohmyorch/hooks/dispatch.sh --mode pre-write` with `only the scoped reviewer/tester may author verdicts`. No file was created. This is one hook on one event. It shows that the plugin's `PreToolUse` hook is delivered and ran from the checkout. Plugin skills and `ohmyorch:*` agents appeared in the session after the install without a restart, also observed once.

## Fixture rehearsals

Synthetic hook events and direct commands against throwaway copies of the working tree. These exercise script logic only, not live event delivery or role identity. [Scripts and logs are versioned here](fixtures/); they ran before the last wording and error-message edits, and contain no secrets. The copies were deleted. Other raw output stays in ignored `.checks/ohmyorch-trial/`, kept only until someone clears it.

| Assertion | Expected | Observed |
|---|---|---|
| `SPECS.md` edit with no active change | Allowed | rc 0 |
| `SPECS.md` edit with a change that has no plan | Refused | rc 2, planning-handoff guard |
| Product file write with a change that has no plan | Refused | rc 2 |
| Main session writes `review.md` | Refused | rc 2 |
| `openspec archive` before gates pass | Refused | rc 2 |
| Stop while the goal is `ACTIVE` | Blocked, names next action | rc 2, `propose` for US-1.1 |
| After `DONE`, next story `BLOCKED` | `escalate` | US-1.2 escalates |
| After `promote` | Loop continues | US-1.2 and US-1.3 `READY`; next action `select` US-1.2 |
| `SPECS.md` edit after a commit, then after a revision refresh | Refused, then allowed | rc 2, then rc 0 |
| Fingerprint across goal start, refresh and Stop | Unchanged | Identical |
| `delivery block --reason`, then Stop | Recorded, allowed | `BLOCKED` with the reason; rc 0 |
| `story_manifest.py capture`, `compare`, then edit a bound file | Pass, pass, fail | rc 0, rc 0, rc 1 naming the file |
| **Premature `DONE` on a story with no change** | Refused | **Allowed, rc 0.** Upstream limit, recorded in Decision 0002 |

**Not established by that table:** the `delivery reopen` refusal. The fixture failed earlier on a missing `tasks.md`, so the refusal rests on reading `delivery.sh:605-611`.

## Not tested

Delegated role identity, a full story lifecycle, `archive` and `mark-done` on a real change, the evidence-review step, resume after remediation, plugin Stop hook delivery in a live session, and real hook payload sizes. Upstream 0.0.1 itself lists live identity and full lifecycle as unproven. The first delivered story must qualify these.

## Review

Static, read-only and not bound to a computed fingerprint. Four passes, whose blocking counts were 6, 3, 1 and 0; two of those findings were introduced by earlier fixes. Findings and dispositions are in the [work record](../../work-items/HARNESS-OHMYORCH-001.md#review), which also lists what was not re-reviewed.

## Final state

The [manifest](verification.json) has the final fingerprint, input manifest reference, requirement mapping and limits. It was generated after the last edit to any fingerprinted input. This summary and the manifest are excluded from that fingerprint.
