# Runbook: epic delivery with OhMyOrch

Runs on this Mac from the repository root, under [Decision 0003](../decisions/0003-openspec-only-delivery.md), [Decision 0030](../decisions/0030-ohmyorch-0-1-0-delivery.md) and [the delivery rule](../../../.claude/rules/ohmyorch-delivery.md). Needs Claude Code, OpenSpec exactly 1.13.2, jq 1.6 or later, Git, and a checkout of [josoroma/OhMyOrch](https://github.com/josoroma/OhMyOrch) on branch `main` at the `upstream.delivery_plugin.commit` in `.claude/autobots.json`, plugin version 0.1.0. On this Mac the checkout is the sibling directory `../OhMyOrch`, recorded as `upstream.delivery_plugin.checkout`.

## Install, once per machine

```sh
claude plugin marketplace add "$(cd ../OhMyOrch && pwd -P)" --scope local
claude plugin install ohmyorch@ohmyorch-marketplace --scope local
```

## Move from 0.0.1

The 0.0.1 install came from `research/upstream/OhMyOrch` on branch `openspec-only`. Replace it, then start a new session:

```sh
claude plugin uninstall ohmyorch@ohmyorch-marketplace --scope local
claude plugin marketplace remove ohmyorch-marketplace --scope local
claude plugin marketplace add "$(cd ../OhMyOrch && pwd -P)" --scope local
claude plugin install ohmyorch@ohmyorch-marketplace --scope local
```

`claude plugin list` then shows `ohmyorch@ohmyorch-marketplace` at 0.1.0, and `/ohmyorch:doctor` passes. The project's managed `CLAUDE.md` block and `openspec/config.yaml` are already at 0.1.0, so `/ohmyorch:adapt-project` is not needed. Its `--apply` would also add four generated `.claude/rules/ohmyorch-*-standards.md` rules and a `README.md` block that this project does not use.

## Deliver

```text
/ohmyorch:deliver EPIC-1
```

The main session then repeats the next action from `delivery next`: `propose` (`/ohmyorch:opsx-propose`), `apply` (`/ohmyorch:opsx-apply`), `verify` (`/ohmyorch:opsx-verify`, ending with a standalone `openspec archive <change> -y`), `mark-done`. A CRITICAL verify finding becomes an unticked task in `tasks.md`, which returns the change to `apply`.

## Stop and resume

A goal stops as `COMPLETE`, `BLOCKED` or `STOPPED`. Stop deliberately with the plugin's `delivery stop`, record a blocker with `delivery block --reason '<story id: the decision needed>'`, and resume with `/ohmyorch:deliver <same target>`. Completed stories are not redone. Another session needs `--takeover`.

## Failure and recovery

| Symptom | Action |
|---|---|
| `/ohmyorch:*` or a removed skill looks stale in a running session | Start a new session |
| Doctor reports OpenSpec `UNSUPPORTED` | Install 1.13.2 explicitly |
| `escalate` on `BLOCKED` after `mark-done` | Run `python3.12 scripts/specs.py promote`. If nothing changes, follow the delivery rule's `BLOCKED` section |
| Archive refused | Read the reason: an unticked task in `tasks.md`, or OpenSpec's own delta-spec validation |
| `Status: DONE` refused | The story's change is still active under `openspec/changes/`. Archive first |
| Post-edit `validate-product-artifacts` failure | Restore the reported field in the mapped document |
| `operation lock exists` | Confirm the process has gone, then follow the upstream recovery notes |

## Exercise status

The 0.0.1 `openspec-only` build was exercised here from US-1.3 on, recorded in each archived change's `verification.md`; US-1.1 and US-1.2 ran under the earlier process. 0.1.0 has not delivered a story here yet. Against this repository its `doctor` passes every check, `validate-product-artifacts` passes with two warnings, and `delivery next` derives `complete` for the recorded goal, all run from the checkout's `bin/ohmyorch` before installation.

## Rollback

To return to 0.0.1, point the marketplace back at `research/upstream/OhMyOrch`, still on branch `openspec-only` at `9f384fa`, and reinstall. Restore the managed `CLAUDE.md` block, `openspec/config.yaml`, `.claude/ohmyorch/managed-files.json` and `SPEC-LOGS/README.md` from the commit before Decision 0030. To remove the plugin and keep project state:

```sh
claude plugin uninstall ohmyorch@ohmyorch-marketplace --scope local
```
