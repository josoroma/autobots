# Decision 0030: deliver with OhMyOrch 0.1.0

**Date:** 2026-11-18. **Authority:** the owner's request to update this repository's OhMyOrch integration to the new checkout at `../OhMyOrch`, which they say "removed what wasn't needed and runs faster". **Supersedes in part:** [Decision 0003](0003-openspec-only-delivery.md), only its plugin pin and its `verification.md` record. Its main-session lifecycle, its trade-off of no independent review, and its boundaries stand.

## Decision

`/ohmyorch:deliver` runs OhMyOrch 0.1.0 from [josoroma/OhMyOrch](https://github.com/josoroma/OhMyOrch) `main` at `2bae070ccef2c5d56a0340ffe73c8a38f55a3031`, recorded as `upstream.delivery_plugin` in `.claude/autobots.json`. That commit is two documentation commits after tag `0.1.0`, with identical plugin files, and it is pushed, unlike the local `openspec-only` branch at `9f384fa` it replaces. `upstream.commit` (`fddfbf5`) stays the ingestor's provenance; the later upstream ingestor wording is not adopted here.

| `openspec-only` build (0.0.1) | 0.1.0 |
|---|---|
| `select` creates the change and sets the story `IN PROGRESS` | No `select`: `propose` creates the change, then the story is set `IN PROGRESS` |
| `implement` | `apply` |
| `verify` writes `verification.md` (`VERIFIED`, `MISMATCH` or `NOT VERIFIED`), checked by `validate-verification` | `verify` writes no file. Each CRITICAL finding becomes an unticked task in `tasks.md` |
| A separate `archive` action, gated on tasks, `verification.md` and `openspec validate` | Archive ends `verify`. The guard refuses only unticked tasks, and OpenSpec validates the delta specs |
| `status.md`, gates and archive conditions | Gone. `tasks.md` is the only tracker |
| Every write ran guard scripts | Only writes to the mapped PRD and SPECS reach a guard, and the Stop hook derives once |

The full upstream list is the plugin's `CHANGELOG.md` at that commit.

## Changes here

- [The bridge rule](../../../.claude/rules/ohmyorch-delivery.md), [the runbook](../runbooks/ohmyorch-delivery.md), `README-DEV.md`'s delivery diagram and `CODEBASE.md`'s pins follow 0.1.0.
- The managed `CLAUDE.md` block was rewritten by the checkout's own `bootstrap --mode merge`, from a reviewed dry-run plan. `openspec/config.yaml` is the 0.1.0 scaffold, recorded in `.claude/ohmyorch/managed-files.json` as `adapt-project` would record it. `SPEC-LOGS/README.md`, a scaffold 0.1.0 no longer creates, is removed with its ledger row.
- `/ohmyorch:adapt-project` was not run: it would also add four generated `.claude/rules/ohmyorch-*-standards.md` rules and a `README.md` block.
- The installed plugin is unchanged. The owner runs the runbook's "Move from 0.0.1" commands, because they change Claude's own configuration.

## What this changes

- A verify result is no longer a file. Each scenario's score is reported in the session and the story's commit message. Archived `verification.md` files stay as history.
- A conditional scenario that is `UNVERIFIED` was archivable with its score visible in `verification.md`, as in US-12.5. Under 0.1.0 a scenario without observed evidence is CRITICAL, so the story stops with `delivery block` for the owner's decision. This follows the plugin's definition; the owner may decide otherwise.
- Not established: 0.1.0 has not delivered a story here. Plugin hook event delivery stays `not_qualified_one_pretooluse_event_observed`.

## Reversal

The runbook's "Rollback" section: point the marketplace back at `research/upstream/OhMyOrch` on `openspec-only`, reinstall, and restore the files above from the commit before this decision.
