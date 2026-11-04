# Runbook: epic delivery with OhMyOrch

**Exercise status:** the install and initialize steps ran on this repository. Deliver, Stop and resume, and Failure and recovery are **not yet exercised live**; some have fixture rehearsals only. The [work item](../work-items/HARNESS-OHMYORCH-001.md) has the step-by-step record, and the first delivered story qualifies them.

## Scope and prerequisites

Runs on this Mac from the repository root. It needs Claude Code, OpenSpec exactly 1.13.2, jq 1.6 or later, Git and the pinned checkout at `research/upstream/OhMyOrch`. See [Decision 0002](../decisions/0002-ohmyorch-delivery-loop.md) for what this authorizes.

`git -C research/upstream/OhMyOrch rev-parse HEAD` must match `upstream.commit` in `.claude/autobots.json`.

## Install, once per machine

```sh
claude plugin marketplace add "$(pwd -P)/research/upstream/OhMyOrch" --scope local
claude plugin install ohmyorch@ohmyorch-marketplace --scope local
claude plugin list
```

Expected: the plugin is listed as enabled at local scope. `.claude/settings.local.json` changes, and Git ignores it. The install also makes a cached copy under `~/.claude/plugins/cache/`, while `claude plugin list` reports reading from the checkout and a live hook was observed running from it. Keep them identical: the bridge rule's pre-start check compares both with the pin. After moving the pin, reinstall.

Observed on Claude Code 2.1.314 in the desktop app: the running session picked up the plugin's skills, agents and hooks within a few turns of the install, without a restart. If `/ohmyorch:*` is missing, start a new session.

## Initialize the project, once

Already applied in this repository. Review the dry run before applying, because `--apply` requires its plan ID.

```sh
plugin_bin="$(pwd -P)/research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch"
"$plugin_bin" --project-root "$(pwd -P)" bootstrap --dry-run --with-openspec --prd PRD-LangChain-Deep-Agents.md --specs SPECS.md --codebase CODEBASE.md --mode merge
"$plugin_bin" --project-root "$(pwd -P)" doctor --json
```

## Deliver

The commit policy in Decision 0002 must be recorded first. Then:

```text
/ohmyorch:doctor --json
/ohmyorch:deliver EPIC-1
```

Expected: doctor passes, and the first action is `select` for US-1.1. Delivery then follows the derived action, plus [the bridge rule](../../../.claude/rules/ohmyorch-delivery.md).

EPIC-1's story order works as written. EPIC-2 and EPIC-4 each stop on a story that depends on a later one, which the bridge rule explains how to handle. EPIC-3 cannot finish before US-4.8 and US-3.4's external decision.

Checkpoints after each story:

```sh
python3.12 scripts/specs.py validate
python3.12 scripts/verify.py --profile harness
```

## Stop and resume

A goal stops as `COMPLETE`, `BLOCKED` (escalation, no progress or `delivery block --reason`) or `STOPPED`. To stop deliberately, run `delivery stop` from the plugin's CLI with the owning `--session-id`. To resume, run `/ohmyorch:deliver <same target>`, including after running `promote` on a `BLOCKED` goal. Completed stories are not redone, and another session needs `--takeover`.

## Failure and recovery

| Symptom | Meaning | Action |
|---|---|---|
| `/ohmyorch:*` is missing | The session has not loaded the plugin | Start a new session and check `claude plugin list` |
| `SPECS.md` edit blocked: `CODEBASE.md describes <rev>, but HEAD has moved on` | A commit moved HEAD past the recorded revision | Refresh `CODEBASE.md` from the diff and record the new revision. The guard's `staleness accepted` suggestion does not unblock it |
| Harness report stale right after a delivery refresh | Should not happen; session state is excluded from the fingerprint | Check `harness_lib.input_manifest` for a new path |
| A DH-W check or `story_manifest.py compare` fails after review and test passed | `delivery reopen` refuses this case, and the verdicts may be stale | Do not archive and do not recapture. Run `delivery block --reason`, report the decision needed, then follow the bridge rule's resume route |
| Stop hook reports "no progress" | A stop condition was not recorded with `delivery block` | Resume, then record the real reason |
| `escalate` on a story whose dependency comes later in `SPECS.md` | Story order, not a product decision | Follow the bridge rule's ordering steps |
| Doctor reports OpenSpec `UNSUPPORTED` | Version is not 1.13.2 | Install 1.13.2 explicitly |
| `SPECS.md` edit blocked for a missing implementation plan | `select` ran in upstream's order | Follow the bridge rule's order, or complete the plan first |
| Post-edit `validate-product-artifacts` failure | A mapped document lost required metadata | Restore the reported field; do not remove the mapping |
| Next action escalates on `BLOCKED` after `mark-done` | `promote` did not run, or the story has a blocker | Run `python3.12 scripts/specs.py promote`. If nothing changes, check its dependencies against the bridge rule |
| `operation lock exists` | A process died during a transaction | Confirm that process has gone, then follow the upstream recovery notes |

## Cleanup and rollback

Remove the plugin and leave project state in place:

```sh
claude plugin uninstall ohmyorch@ohmyorch-marketplace --scope local
```

Bootstrap's recovery ID is in the work item. Inspect a rollback first; it verifies hashes and refuses to overwrite later edits.

```sh
"$plugin_bin" --project-root "$(pwd -P)" upgrade-project --dry-run --rollback <recovery-id>
```

Never remove `.claude/ohmyorch/runtime` or its backups wholesale.
