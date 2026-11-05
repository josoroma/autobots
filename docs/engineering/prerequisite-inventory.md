# Repository and prerequisite inventory

**Story:** US-1.1 (EPIC-1, phase reference H0-01). **Sources:** SP-001 item 1, DH-02 H0.1, SP-020.

**Observed:** 2026-11-04, on this Mac. **Base revision:** `34ae38f591dc2809d95819433bdceb2fb17b9e27`, with uncommitted delivery records for US-1.1 and the five `.gitignore` rules described under [Repository hygiene](#repository-hygiene) in the working tree.

**Shell:** zsh (`/bin/zsh`), run by the assistant's Bash tool from the repository root and initialized from the user's profile. The search path was not printed, so results from another shell or process may differ.

**Presence is not H0/H1 qualification.** This is a point-in-time record of what exists. It does not establish that H0, H1 or product acceptance passed, that any asset works, or that any installed tool version is suitable. Compatibility belongs to US-1.3.

## Repository

| Item | Value | Command |
|---|---|---|
| Version control | Git work tree | `git rev-parse --is-inside-work-tree` |
| Current branch | `delivery/epic-1` | `git branch --show-current` |
| Branches | `delivery/epic-1`, `main` | `git branch --format='%(refname:short)'` |
| Remote names | None: the command prints nothing | `git remote` |
| Commits on the current branch | 2 | `git log --oneline \| wc -l` |

Remote URLs and Git configuration were not read.

### Tracked files by top-level path

There are 159 tracked files at the base revision. Reproduce the table below with:

```sh
git ls-tree -r --name-only 34ae38f | awk -F/ '{print $1}' | sort | uniq -c
```

`git ls-files` gave the same counts at observation. It will stop matching once this story's commit adds files, so later checks should use the command above.

| Top-level path | Tracked files |
|---|---|
| `.claude` | 41 |
| `.gitignore` | 1 |
| `AGENTS.md` | 1 |
| `CLAUDE.md` | 1 |
| `CODEBASE.md` | 1 |
| `docs` | 53 |
| `openspec` | 4 |
| `PRD-AutoGPT.md` | 1 |
| `PRD-Comparison-Recommendation.md` | 1 |
| `PRD-Design-System.md` | 1 |
| `PRD-Development-Harness.md` | 1 |
| `PRD-LangChain-Deep-Agents.md` | 1 |
| `PRD-Local-Mac-Deployment.md` | 1 |
| `PRD-Model-Providers.md` | 1 |
| `PRD-NextJS.md` | 1 |
| `README.md` | 1 |
| `research` | 39 |
| `scripts` | 4 |
| `SPEC-LOGS` | 1 |
| `SPECS.md` | 1 |
| `tests` | 3 |

### Documentation and project-local development assets

Each path passed `test -e`. Tracked counts come from `git ls-files -- <path>`.

| Path | Tracked files | Contents |
|---|---|---|
| `PRD-AutoGPT.md` | 1 | Product requirements document |
| `PRD-Comparison-Recommendation.md` | 1 | Product requirements document |
| `PRD-Design-System.md` | 1 | Product requirements document |
| `PRD-Development-Harness.md` | 1 | Product requirements document |
| `PRD-LangChain-Deep-Agents.md` | 1 | Product requirements document |
| `PRD-Local-Mac-Deployment.md` | 1 | Product requirements document |
| `PRD-Model-Providers.md` | 1 | Product requirements document |
| `PRD-NextJS.md` | 1 | Product requirements document |
| `SPECS.md` | 1 | Execution backlog |
| `CODEBASE.md` | 1 | Descriptive codebase context |
| `AGENTS.md` | 1 | Shared engineering instructions |
| `CLAUDE.md` | 1 | Assistant entry point |
| `.claude/` | 41 | Agents, hooks, rules, skills, `autobots.json`, `settings.json`, `ohmyorch/` |
| `docs/` | 53 | `design/`, `engineering/`, `imagine/` |
| `scripts/` | 4 | `harness_lib.py`, `specs.py`, `story_manifest.py`, `verify.py` |
| `tests/harness/` | 3 | `test_hooks.py`, `test_specs.py`, `test_story_manifest.py` |
| `openspec/` | 4 | `config.yaml`, `changes/`, `delivery/`, `specs/` |
| `SPEC-LOGS/` | 1 | `README.md` |
| `research/` | 39 | Research material. `research/upstream/` also exists here, ignored and not repository input |

## Local tools

Install paths come from `which -a <tool>` in the shell above. `which -a` lists only what is on that shell's search path, and it repeated some entries, so each path appears once below in first-seen order. `ls ~/.nvm/versions/node/` found only the two nvm versions listed.

The version is the first line of standard output from that path's own command. Docker commands are client-only. **This table records no compatibility verdict.**

| Tool | Source that names it | Install path | Version | Probe | Status |
|---|---|---|---|---|---|
| Git | `.claude/rules/ohmyorch-delivery.md`; OhMyOrch `doctor`. H0.1 says "version control" without naming a tool | `/usr/bin/git` | git version 2.54.0 (Apple Git-157) | `/usr/bin/git --version` | present |
| Python 3.12 | H0.3; SP-001 item 3 | `/opt/homebrew/bin/python3.12` | Python 3.12.16 | `/opt/homebrew/bin/python3.12 --version` | present |
| Python 3.12 | H0.3; SP-001 item 3 | `/Users/josoroma/.local/bin/python3.12` | Python 3.12.9 | `/Users/josoroma/.local/bin/python3.12 --version` | present |
| uv | H0.3; SP-001 item 3 | `/opt/homebrew/bin/uv` | uv 0.13.6 (Homebrew 2026-10-26 aarch64-apple-darwin) | `/opt/homebrew/bin/uv --version` | present |
| uv | H0.3; SP-001 item 3 | `/Users/josoroma/.local/bin/uv` | uv 0.11.18 (e32666915 2026-06-01 aarch64-apple-darwin) | `/Users/josoroma/.local/bin/uv --version` | present |
| Node | H0.3; SP-001 item 3 | `/opt/homebrew/bin/node` | v26.13.0 | `/opt/homebrew/bin/node --version` | present |
| Node | H0.3; SP-001 item 3 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/node` | v22.23.2 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/node --version` | present |
| Node | H0.3; SP-001 item 3 | `/Users/josoroma/.local/bin/node` | v22.22.3 | `/Users/josoroma/.local/bin/node --version` | present |
| Node | H0.3; SP-001 item 3 | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/node` | v22.13.1 | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/node --version` | present |
| pnpm | H0.3; SP-001 item 3 | None found | None | `command -v pnpm` | **missing** |
| npm | US-1.1 task 1.2. `PRD-NextJS.md` names the npm registry, not a local tool | `/opt/homebrew/bin/npm` | 11.20.0 | `/opt/homebrew/bin/npm --version` | present |
| npm | US-1.1 task 1.2 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/npm` | 10.9.8 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/npm --version` | present |
| npm | US-1.1 task 1.2 | `/Users/josoroma/.local/bin/npm` | 10.9.8 | `/Users/josoroma/.local/bin/npm --version` | present |
| npm | US-1.1 task 1.2 | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/npm` | 10.9.2 | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/npm --version` | present |
| Corepack | US-1.1 task 1.2 only: no tracked file names it | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/corepack` | 0.34.6 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/corepack --version` | present |
| Corepack | US-1.1 task 1.2 only | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/corepack` | 0.30.0 | `/Users/josoroma/.nvm/versions/node/v22.13.1/bin/corepack --version` | present |
| Docker client | `PRD-Local-Mac-Deployment.md` | `/usr/local/bin/docker` | Docker version 29.9.2, build a82e528 | `/usr/local/bin/docker --version` | present |
| Docker Compose | `PRD-Local-Mac-Deployment.md` | `/usr/local/bin/docker` (`compose` subcommand) | Docker Compose version v5.6.1 | `/usr/local/bin/docker compose version` | present |
| Docker Compose | `PRD-Local-Mac-Deployment.md` | `/usr/local/bin/docker-compose` | Docker Compose version v5.6.1 | `/usr/local/bin/docker-compose version` | present |
| Docker Compose | `PRD-Local-Mac-Deployment.md` | `/Users/josoroma/.docker/cli-plugins/docker-compose` | Docker Compose version v5.6.1 | `/Users/josoroma/.docker/cli-plugins/docker-compose version` | present |
| Supabase CLI | `PRD-Local-Mac-Deployment.md` | `/opt/homebrew/bin/supabase` | 2.98.2 | `/opt/homebrew/bin/supabase --version` | present |
| jq | `.claude/rules/ohmyorch-delivery.md`; OhMyOrch `doctor` | `/usr/bin/jq` | jq-1.7.1-apple | `/usr/bin/jq --version` | present |
| Bash | OhMyOrch `doctor` | `/bin/bash` | GNU bash, version 3.2.57(1)-release (arm64-apple-darwin26) | `/bin/bash --version` | present |
| OpenSpec | Decision 0002; OhMyOrch `doctor` | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/openspec` | 1.13.2 | `/Users/josoroma/.nvm/versions/node/v22.23.2/bin/openspec --version` | present |
| Claude Code | `PRD-Development-Harness.md` | `/opt/homebrew/bin/claude` | 2.1.314 (Claude Code) | `/opt/homebrew/bin/claude --version` | present |

**Missing prerequisite:** `pnpm`. `command -v pnpm` and `which -a pnpm` both exit 1. `corepack pnpm` was not run, so nothing here says whether Corepack could supply it.

### Notes on the installs

- **`python3` is a zsh alias.** `alias python3` prints `python3=/opt/homebrew/opt/python@3.12/bin/python3.12`, which reports Python 3.12.16. Outside the alias, `which -a python3` finds `/opt/homebrew/bin/python3` (Python 3.15.2) and `/usr/bin/python3` (Python 3.9.6). `/usr/bin/env python3 --version` prints Python 3.15.2 in this shell.
- **Symbolic links.** `ls -l` shows that:
  - `/usr/local/bin/docker` links to `/Applications/Docker.app/Contents/Resources/bin/docker`.
  - `/usr/local/bin/docker-compose` and `/Users/josoroma/.docker/cli-plugins/docker-compose` both link to `/Applications/Docker.app/Contents/Resources/cli-plugins/docker-compose`.
  - `/Users/josoroma/.local/bin/node` and `npm` link under `/Users/josoroma/.hermes/node/bin/`.
  - `/Users/josoroma/.local/bin/python3.12` links under `/Users/josoroma/.local/share/uv/python/`.
- **npm, Corepack and OpenSpec are Node scripts.** Each path starts with `#!/usr/bin/env node`, so it runs under the first `node` on the search path rather than the Node directory it is installed in. In this shell, `/usr/bin/env node --version` prints v26.13.0.
- **Supabase CLI network note.** `/opt/homebrew/bin/supabase --version` appears to make an outbound update check. Run normally, it also wrote an update notice to standard error, naming v3.0.0 as available. Review F-1 reports that with network access denied it printed `2.98.2`, exit 0, with no notice. This is inferred from that behavior, not from a packet capture, and no other version probe was tested for this. The notice is not part of the recorded version and is not a recommendation.

### Not inspected

- Docker engine state, disk, ports and ARM64 image availability (LM-03). `docker version` and `docker info` contact the engine and were not run.
- `.env` files. Their paths were treated as strings only, for ignore checks. Neither their contents nor their existence was probed.
- The contents of `.claude/settings.local.json`. `test -e` confirmed that it exists, and it was not opened.
- The provider master-key file, which was **not probed**. `PRD-Model-Providers.md` places it outside the repository.
- The process environment and search path, which were not printed.

## `CODEBASE.md` reconciliation

This compares every statement under `Runtime and Tooling` in the working-tree `CODEBASE.md` with the probes above. This comparison edited nothing; the coordinator owns `CODEBASE.md`. "Omits" means that the statement holds but leaves out an observed install.

| Statement | Result | Basis |
|---|---|---|
| Observed on 2026-11-04, on this Mac | Could not check | That observation cannot be re-run. This inventory's observations carry the same date |
| Presence is not qualification of an application environment | Could not check | This is a limit rather than something a probe can test. This inventory states the same limit |
| Python 3.12.16 at `/opt/homebrew/bin/python3.12` | Matches; omits | Omits `/Users/josoroma/.local/bin/python3.12` (Python 3.12.9) |
| That Python is used by project hooks | Matches | `.claude/settings.json` names it as the command in 5 hook entries |
| That Python is used by project scripts | Differs in part | The three entry points, `scripts/specs.py`, `scripts/story_manifest.py` and `scripts/verify.py`, do not name that path. They are not executable, and their `#!/usr/bin/env python3` line resolves to Python 3.15.2 in this shell. They run under this Python when started with the documented `python3.12 scripts/...` commands, where it is the first `python3.12` found. Each checks for 3.12 or later, not this install. `scripts/harness_lib.py` is a module that `scripts/verify.py` imports, with no shebang or version check of its own |
| OpenSpec 1.13.2 | Matches | Same version |
| jq 1.7.1 | Matches | The tool prints `jq-1.7.1-apple`, with a vendor suffix the statement leaves out |
| Bash 3.2.57 | Matches | Same version |
| Claude Code 2.1.314 | Matches | Same version |
| OpenSpec, jq and Bash are used by OhMyOrch delivery | Matches | OhMyOrch `doctor` checks all three, and its entry point starts with `#!/bin/bash` |
| Claude Code is used by OhMyOrch delivery | Could not check | No probe in this story ties delivery to this executable |
| Node 26.13.0 is present | Matches; omits | Omits the three other Node installs in the tool table |
| uv 0.13.6 is present | Matches; omits | Omits `/Users/josoroma/.local/bin/uv` (uv 0.11.18) |
| Supabase CLI 2.98.2 is present | Matches | Same version |
| Docker 29.9.2 is present | Matches; omits | This is the client version. The statement does not say so, and the engine was not inspected. Docker Compose is not mentioned |
| pnpm is absent | Matches | `command -v pnpm` exits 1 |

The section also does not mention Git, npm or Corepack, all of which are present.

**Outside that section:** `CODEBASE.md`, under `Upstream evidence and local constraints`, says a separate process resolved plain `python3` to macOS 3.9.6. In this shell `/usr/bin/env python3` resolves to 3.15.2. The result depends on the process's search path, so the two observations can both be true. That earlier process was not reproduced.

## Repository hygiene

This section records what "Scenario: Establish repository hygiene" found absent and what this story changed. The scenario's Given is *version control or required ignores are absent*. The Tester, not this document, scores the scenario.

- **Absent at the base revision:** rules for five cache categories under DH-03's "caches": `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.tsbuildinfo` and `.pnpm-store/`.
- **Added by this story:** those five rules and nothing else, under the user's decision of 2026-11-04, recorded in Decision 0002. They are at `.gitignore` lines 25 to 29, outside the `OHMYORCH` managed block, and were uncommitted at observation.
- **Predates this story:** version control and every other ignore rule. `git log --format='%h' -- .gitignore` lists `34ae38f` and `5e46124`, and lines 1 to 24 of `.gitignore` are identical to the base revision.
- **Still without a rule:** local transcripts, by the user's decision, and the other caches in the table below.

Each sample uses `git check-ignore -q --no-index <sample path>`, where exit 0 means ignored and exit 1 means not ignored. The samples are path strings and do not need to exist. The required categories come from DH-03.

| Item | Probe | Result | Evaluation | Basis |
|---|---|---|---|---|
| Version control | `git rev-parse --is-inside-work-tree` | Prints `true`, exit 0 | Present. Predates this story | Observation |
| `.env` files | Samples `.env`, `.env.local` | Exit 0 for each | Rule predates this story | Observation |
| `.env.example` | Sample `.env.example` | Exit 1 | Not ignored, through the `!.env.example` rule in `.gitignore` | Observation |
| `.claude/settings.local.json` | Sample `.claude/settings.local.json` | Exit 0 | Rule predates this story | Observation |
| `.checks` outputs | Sample `.checks/x` | Exit 0 | Rule predates this story | Observation |
| Caches: rule predates this story | Samples `.venv/x`, `node_modules/x`, `.next/x`, `scripts/__pycache__/a.pyc`, `.DS_Store` | Exit 0 for each | Rule predates this story | Observation |
| Caches: rule added by this story | Samples `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo`, `apps/web/tsconfig.tsbuildinfo`, `.pnpm-store/x` | Exit 0 for each, and `git check-ignore -v --no-index` names `.gitignore` lines 25 to 29. Each exited 1 before the rules were added | **Added by this story** | Observation. User decision for adding them |
| Caches: no rule | Samples `.eslintcache`, `.coverage`, `coverage/x`, `.hypothesis/x`, `.cache/x`, `.turbo/x`, `.uv/x` | Exit 1 for each | **No rule exists, and these are not claimed as covered.** A later story adds ignores for the tools it introduces | Observation. User decision for leaving them out |
| Disposable data | Samples `infra/supabase/volumes/x`, `supabase/.temp/x`, `supabase/.branches/x`, `x.log` | Exit 0 for each | Rule predates this story | Observation |
| Local transcripts | Samples `transcript.jsonl`, `transcripts/x.md`, `.claude/projects/x.jsonl` | **Exit 1 for each: no ignore rule exists** | **Not missing, by user decision only** | **User decision OQ-1, 2026-11-04. Not a probe result** |
| Tracked files matching an ignore rule | `git ls-files -ci --exclude-standard` | No output, exit 0 | No tracked file is ignored | Observation |
| Provider master-key file | Not probed | Not applicable | No repository rule is needed if it stays where the source places it | `PRD-Model-Providers.md` |

### What the cache rules do and do not show

**DH-03 gives no closed cache list.** It says to ignore "caches" without naming them, so this inventory does not say every cache is covered. The user decided that these five rules close the cache question for this story, and that a later story introducing a tool adds that tool's ignores.

The rules are shown on sample paths only. `test -e` exits 1 for `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and `.pnpm-store`, `find` lists no `*.tsbuildinfo` outside `.git` and `research/upstream`, and no cache tool was run. How real tools' output matches these rules is unobserved.

### The local-transcripts gap

DH-03 says to ignore local transcripts, and the probes show no rule for them, before and after the five cache rules were added. On the probes alone, this required category has no rule. It counts as "not missing" only because the user decided so on 2026-11-04 (OQ-1): no source names an in-repository transcript location. The decision adds no rule.

**A future in-repository transcript location is uncovered until a rule is added.** Nothing in Git would stop a transcript at such a location from being committed.

### Filename scan

These commands look at names only and do not inspect file contents:

```sh
git log --all --name-only --format= | sort -u | grep -i -E '(^|/)\.env|\.key$|\.pem$|\.p12$|secret|credential|transcript|\.jsonl$|\.sqlite|\.db$|/volumes/|settings\.local'
git ls-files --others --exclude-standard | grep -i -E 'transcript|\.jsonl$'
```

- The history scan lists one name, `research/qwen38-gguf-memory.jsonl`. The field names in its first record are `pressure_level`, `rss_bytes`, `server_pid`, `swap_used_bytes` and `time_utc`, so that record is a memory sample rather than a conversation. Other records were not inspected.
- The scan of untracked, non-ignored files lists nothing and exits 1. It does not cover ignored paths such as `.checks/` and `research/upstream/`.

These results show only that no such names turned up. A credential or transcript under an unremarkable name would not appear.

### What was changed

No `git init` was run. The only change to `.gitignore` is the five rules. The coordinator wrote them verbatim from the implementer's lines, because `.gitignore` is a protected path. These commands show it, run before the story's commit:

```sh
git show 34ae38f:.gitignore | grep -cE '^(\.pytest_cache/|\.ruff_cache/|\.mypy_cache/|\*\.tsbuildinfo|\.pnpm-store/)$'
git show 34ae38f:.gitignore | diff - <(sed -n '1,24p' .gitignore)
grep -n 'OHMYORCH:END' .gitignore
sed -n '25,$p' .gitignore
git diff -U0 HEAD -- .gitignore | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)'
```

- The first prints `0`, so the base revision had none of the five rules. Its grep exits 1 on a zero count, so read the output rather than the exit code.
- The second prints nothing and exits 0, so lines 1 to 24 are unchanged.
- The third prints `24:# OHMYORCH:END ignores`, and the fourth prints the five rules in the order listed above.
- The fifth prints the five rules, each prefixed `+`, and no `-` line.

## Secret and overwrite checks

The inventory names secret-bearing files by name only. None was read.

```sh
grep -l -E 'sk-or-v1-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}' docs/engineering/prerequisite-inventory.md
git diff --quiet HEAD -- .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests
```

Both behaved as expected on this file: the first lists nothing and exits 1, and the second exits 0. `.gitignore` is left out of the second command because this story changes it. [What was changed](#what-was-changed) shows that only the five rules were added.

**Limit of the secret scan:** it covers only these four credential shapes, so a clean result does not prove that no secret is present.

**Limit of the overwrite check:** `.claude/settings.local.json` is ignored and must not be read, and assistant permission approvals can legitimately change it. Non-overwrite therefore cannot be shown mechanically. The evidence is limited to no write to it being attempted while producing this inventory.

## Reproducing this inventory

Run the commands recorded in each section from the repository root. Tool probes use the absolute paths in the table, so the install being probed does not depend on search order.

**Network:** re-running `/opt/homebrew/bin/supabase --version` appears to repeat an outbound update check, as described in the [Supabase CLI network note](#notes-on-the-installs). No other version probe was tested for this.

**After the story's commit:** commands comparing with `HEAD` will stop showing this story's changes. Use `34ae38f` in their place.

Do not read `.env` files, the provider master-key file or `.claude/settings.local.json`. Do not print the environment or remote URLs, run `docker version` or `docker info`, run any Corepack command other than `--version`, or install or start anything.
