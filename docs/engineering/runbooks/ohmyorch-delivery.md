# Runbook: epic delivery with OhMyOrch

Runs on this Mac from the repository root, under [Decision 0003](../decisions/0003-openspec-only-delivery.md) and [the delivery rule](../../../.claude/rules/ohmyorch-delivery.md). Needs Claude Code, OpenSpec exactly 1.13.2, jq 1.6 or later, Git, and the checkout at `research/upstream/OhMyOrch` on branch `openspec-only`, at the `upstream.delivery_plugin.commit` in `.claude/autobots.json`. That branch is local and not pushed.

## Install, once per machine

```sh
claude plugin marketplace add "$(pwd -P)/research/upstream/OhMyOrch" --scope local
claude plugin install ohmyorch@ohmyorch-marketplace --scope local
```

After moving the checkout, reinstall: uninstall, then install. The version stays 0.0.1, so an update alone will not refresh the cached copy.

## Deliver

```text
/ohmyorch:deliver EPIC-1
```

The main session then repeats the next action from `delivery next`: `select`, `propose` (`/ohmyorch:opsx-propose`), `implement` (`/ohmyorch:opsx-apply`), `verify` (`/ohmyorch:opsx-verify`, recorded in the change's `verification.md`), `archive` (a standalone `openspec archive <id> -y`), `mark-done`. A failed verification returns to `implement`.

## Stop and resume

A goal stops as `COMPLETE`, `BLOCKED` or `STOPPED`. Stop deliberately with the plugin's `delivery stop`, record a blocker with `delivery block --reason "<text>"`, and resume with `/ohmyorch:deliver <same target>`. Completed stories are not redone. Another session needs `--takeover`.

## Failure and recovery

| Symptom | Action |
|---|---|
| `/ohmyorch:*` or a removed agent looks stale in a running session | Start a new session |
| Doctor reports OpenSpec `UNSUPPORTED` | Install 1.13.2 explicitly |
| `escalate` on `BLOCKED` after `mark-done` | Run `python3.12 scripts/specs.py promote`. If nothing changes, follow the delivery rule's `BLOCKED` section |
| Archive refused | Read the reason: tasks incomplete, verification missing or failing, or `openspec validate` errors |
| Post-edit `validate-product-artifacts` failure | Restore the reported field in the mapped document |
| `operation lock exists` | Confirm the process has gone, then follow the upstream recovery notes |

## Exercise status

Exercised on this repository through US-1.3, recorded in its archived `verification.md`. The earlier stories ran under the previous process. The plugin's own tests and a fixture rehearsal pass at the pinned commit; the first live pass of the simplified skills is US-1.3 onward.

## Rollback

See Decision 0003. To remove the plugin and keep project state:

```sh
claude plugin uninstall ohmyorch@ohmyorch-marketplace --scope local
```
