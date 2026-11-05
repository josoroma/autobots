# Proposal

Story: US-1.1
Change: us-1-1-h0-repository-prerequisite-inventory

## Why

Existing work and missing prerequisites must be visible before H0 changes begin (SP-001 item 1, DH-02 H0.1, SP-020 H0-01). `CODEBASE.md` holds only a partial tool list: it omits Git, npm and Docker Compose, gives a path only for Python, and names one install each of Node and uv where several exist.

## What Changes

- Add a versioned inventory at `docs/engineering/prerequisite-inventory.md` (assumption A1) recording actual paths, versions and missing prerequisites, with no secret values.
- Record in that inventory whether each version-control and required-ignore item is present, with the probe that shows it.
- Add `.gitignore` rules for five cache categories: `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo` and `.pnpm-store/`. DH-03 says "caches" with no in-use limit, and the user decided on 2026-11-04 to add these in this story (review finding F-6). This is the only version-control or ignore change, and it uses the protected-path procedure.
- Change nothing else in version-control or ignore configuration. Version control exists, the other ignore categories with a concrete path have rules, and the user decided local transcripts are not missing (OQ-1), so no transcript rule is added.
- Add no tool, test framework or dependency. The inventory records the commands that reproduce it.

## Observed Current State

Observed by the Planner on 2026-11-04 at base revision `34ae38f`. The Implementer re-probes; these values are not the deliverable.

**Scenario "Establish repository hygiene", Given clause: "version control or required ignores are absent".**

| Item (source) | Evaluates today | Evidence |
|---|---|---|
| Version control (H0.1, SP-001) | Not absent | `git rev-parse --is-inside-work-tree` prints `true`; 2 commits; branches `main`, `delivery/epic-1`; no remote |
| `.env` files (DH-03, LM-06) | Not absent | `git check-ignore --no-index`: `.env` and `.env.local` ignored; `.env.example` kept by design |
| `.claude/settings.local.json` (DH-03, SP-001) | Not absent | Ignored; present locally and not read |
| `.checks` outputs (DH-03) | Not absent | `.checks/x` ignored |
| **Caches (DH-03)** | **Absent for five categories at the base revision, so the Given holds** | Rules exist for `__pycache__/`, `*.py[cod]`, `.venv/`, `node_modules/`, `.next/` and `.DS_Store`. At `34ae38f`, `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo` and `.pnpm-store/x` exit 1 under `git check-ignore --no-index`. None of those five exists on disk. This story adds their rules. DH-03 gives no closed list of caches (see Open Questions) |
| Disposable data (DH-03) | Not absent | `infra/supabase/volumes/`, `supabase/.temp/`, `supabase/.branches/`, `*.log` ignored |
| Provider master key (PRD-Model-Providers, LM-06) | No repository rule needed | The source places it under `~/Library/Application Support/Autobots/secrets/`, outside the repository |
| **Local transcripts (DH-03)** | **No rule. Not missing by user decision only (OQ-1)** | `transcript.jsonl`, `transcripts/x.md` and `.claude/projects/x.jsonl` exit 1 before and after this change. "Not missing" is the user's decision, not a probe result. No source names an in-repository transcript path, and no transcript file was found by name in Git history or in the worktree. This story establishes nothing for this category |

At the base revision the scenario's Then clause was not met for the five cache categories. Separately, nothing forbidden was found committed:

- A filename scan across all Git history found one candidate, `research/qwen38-gguf-memory.jsonl`. Its first record holds only memory-sample fields (`time_utc`, `rss_bytes`, `swap_used_bytes`, `pressure_level`, `server_pid`).
- `research/qwen38-gguf-session.json` holds phase and host-memory events. Only its structure was inspected, and it looks like an experiment record rather than a conversation.
- A narrow secret-shape scan listing filenames only found no match in any commit. This does not prove absence.

**Tools.** Missing: `pnpm`. Present (first path found, version):

- Git: `/usr/bin/git`, 2.54.0
- Python 3.12: `/opt/homebrew/bin/python3.12`, 3.12.16
- uv: `/opt/homebrew/bin/uv`, 0.13.6
- Node: `/opt/homebrew/bin/node`, 26.13.0
- npm: `/opt/homebrew/bin/npm`, 11.20.0
- Docker client: `/usr/local/bin/docker` (links into `/Applications/Docker.app`), 29.9.2
- Docker Compose: 5.6.1
- Supabase CLI: `/opt/homebrew/bin/supabase`, 2.98.2
- jq: `/usr/bin/jq`, 1.7.1-apple
- Bash: `/bin/bash`, 3.2.57
- OpenSpec: under nvm Node v22.23.2, 1.13.2
- Claude Code: `/opt/homebrew/bin/claude`, 2.1.314

Multiple installs exist:

- `node`: also v22.23.2 and v22.13.1 under nvm, and v22.22.3 at `~/.local/bin`
- `uv`: also 0.11.18 at `~/.local/bin`
- `python3`: a shell alias to Python 3.12, plus `/opt/homebrew/bin/python3` (3.15.2) and `/usr/bin/python3` (3.9.6)
- `corepack`: only under nvm

## Capabilities

### New Capabilities
- `repository-prerequisite-inventory`: an accurate repository and local-tool inventory, and establishing version control and required ignores only where absent.

### Modified Capabilities
None. `openspec list --specs` reports no existing specs.

## Non-Goals

- US-1.2 onward, including shared instructions and assistant assets (US-1.2), portable verification and hooks (US-1.4), work-record templates (US-1.5) and H1 qualification (US-1.6 to US-1.8).
- Toolchain locking and scaffolding (US-1.3): no `pnpm` install, no Corepack activation, no manifests or lockfiles, no choice of Node or uv install, and no verdict on whether an installed version is compatible.
- Ignore rules beyond the five named cache categories, including any rule for local transcripts. Adding these rules installs and adopts none of those tools. A later story that introduces a tool adds that tool's ignores (user decision).
- Any install, service or Docker engine start, database change or model call. Engine state, disk, ports and ARM64 image checks (LM-03) are not inspected; only client versions are recorded.
- Reading or printing `.env` files, the provider master key file, `.claude/settings.local.json` or environment dumps.
- Removing or relocating existing tracked files, including historical `research/` evidence.
- Any claim that H0/H1 or product acceptance passed. Presence of a tool or asset is not qualification.

## Impact

- **Added:** `docs/engineering/prerequisite-inventory.md`.
- **Protected path:** `.gitignore`, five lines appended after the managed `# OHMYORCH:END ignores` line. The Implementer authors them, the coordinator writes them verbatim before capture, and the reviewer checks them as implementation.
- **Unchanged:** the Git configuration and the managed `OHMYORCH` block.
- **Coordinator-owned records and routine files:** `SPECS.md`, `CODEBASE.md`, `openspec/changes/us-1-1-h0-repository-prerequisite-inventory/`, `openspec/delivery/goal.md`, `docs/engineering/work-items/US-1.1.md` (the H0.1 plan record) and `docs/engineering/evidence/US-1.1/`.
- **Coordinator decision records landing in this story's commit:** `.claude/rules/ohmyorch-delivery.md` and `docs/engineering/decisions/0002-ohmyorch-delivery-loop.md`. They are not part of this story's acceptance.
- **APIs, schema, dependencies, services:** none.
- **Network:** `supabase --version`, a recorded inventory probe, appears to make an outbound update check (review finding F-1).
- **Generated output:** only Git-ignored `.checks/` files and `__pycache__` bytecode.

## Assumptions For The Coordinator

- **A1, inventory location.** DH-02 H0.1 requires an "Inventory" but names no path, and DH-W01 and DH-W04 fix only the work-record and evidence paths. `docs/engineering/prerequisite-inventory.md` is proposed. Accepted by the coordinator: it is a documentation path, and the alternatives are records excluded from the reviewed manifest.
- **A2, runbook.** Operating behavior is unchanged, so DH-W05 is met by saying so and referencing `docs/engineering/runbooks/development-harness.md` plus `python3.12 scripts/verify.py --profile harness`. The inventory carries its own reproduction commands, and no new runbook is created. Accepted by the coordinator.
- **A3, absolute paths.** Home-directory paths are recorded verbatim because the scenario requires actual paths. They are not secret values, and tracked evidence already contains them.

## Open Questions

None open.

Decided:

- **OQ-1, decided by the user on 2026-11-04:** DH-03 says to ignore local transcripts, but `.gitignore` has no such rule and no source says where an in-repository transcript would live. Decision: record it as not missing, and add no rule. The inventory states the gap: a future in-repository transcript location would be uncovered until a rule is added.
- **Cache ignores, decided by the user on 2026-11-04:** add the five named cache rules in this story, not in US-1.3 (review finding F-6).
- **Cache list, decided by the user on 2026-11-04:** those five close the cache question for US-1.1. Other cache-shaped samples also have no rule (`.eslintcache`, `.coverage`, `coverage/x`, `.hypothesis/x`, `.cache/x`, `.turbo/x`, `.uv/x` all exit 1), and a later story that introduces a tool adds that tool's ignores. No record may say every cache is covered.
