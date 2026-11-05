# Test Report — us-1-1-h0-repository-prerequisite-inventory

Change: us-1-1-h0-repository-prerequisite-inventory
Story: US-1.1
Verdict: pass
Coverage: 1/2 acceptance criteria evaluated
Reviewed fingerprint: 69df0ac2b649fe796d6b48a534faa42e6135ede6311fbf3b7e48d2526acbdbb8

Tester: `ohmyorch:tester`, a delegated context separate from the implementer, reviewer and coordinator. All evidence is `static` or a re-run local probe, with model transport none.

**What this verdict means.** The report format allows only `pass` or `fail`, and `fail` requires a failing criterion. No criterion failed, and one passed. **One of the two scenarios was not exercised and has no acceptance evidence.** This verdict does not say that US-1.1's acceptance is fully verified, and it does not establish H0, H1 or product acceptance.

**Why coverage is partial.** "Establish repository hygiene" is `UNVERIFIED`: its When and Then were not exercised, so its Then cannot be evaluated.

## Acceptance Criteria Evaluated

| # | Scenario | Result | Evidence |
|---|---|---|---|
| 1 | Preserve existing work | PASS | Re-run probes matched the inventory. All 24 tool version commands returned the recorded value; all 19 asset paths passed `test -e`; 159 tracked files with matching per-path counts at `34ae38f`; `command -v pnpm` and `which -a pnpm` exit 1, recorded as missing. The narrow secret scan exits 1 and a wider scan has 0 hits for every shape. `git diff --quiet HEAD -- .gitignore .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests` exits 0. Inspection: every statement under `Runtime and Tooling` in `CODEBASE.md` has a reconciliation row, and the tool table has only `present` and `missing` statuses, with no compatibility verdict. Limits are under "Limits on criterion 1". |
| 2 | Establish repository hygiene | UNVERIFIED | Given checked first. **The Given does not hold only once two scoping calls are applied; the probes alone do not show it.** (a) Version control rests on a probe I ran: `git rev-parse --is-inside-work-tree` printed `true`, exit 0. (b) Concrete-path ignores rest on probes I ran: 13 `git check-ignore -q --no-index` samples exit 0. (c) Local transcripts rest on the user's decision OQ-1 as recorded: `transcript.jsonl`, `transcripts/x.md` and `.claude/projects/x.jsonl` exit 1, and no rule exists. (d) The five cache categories (`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `*.tsbuildinfo`, `.pnpm-store`) rest on a coordinator scoping call deferring them to US-1.3: samples exit 1, no rule exists, and there is no user decision. **When and Then were not exercised, and this story established nothing.** `git diff --quiet HEAD -- .gitignore` exits 0, and `.gitignore` history is `34ae38f`, `5e46124`, both before this story. |

## Limits on criterion 1

- **Secret scans.** They cover only the listed shapes, so a clean result does not prove that no secret is present. I also read the whole inventory: it refers to "the provider master-key file" in prose only. I did not run a mechanical check for that filename, because this task forbids naming it in a command.
- **`.claude/settings.local.json`.** Non-overwrite was not shown. The file was not read or stat-ed, and the plan (line 138) records that this cannot be shown mechanically. The non-overwrite part of the Then is observed for tracked settings only. For this file it rests on the implementer's statement that no write was attempted, which I could not observe.
- **Install paths.** They are complete only for this shell's search path, as inventory line 85 discloses. `/Users/josoroma/.hermes/node/bin/corepack` exists (`test -e` exit 0) and is not listed.
- **`check-scope`.** `IN SCOPE` is weak evidence, because any path named in the plan counts as predicted. The `git diff --quiet` check covers the paths that must not change.
- **Point in time.** These results show that the values hold now, on this Mac, in this shell.

## Given analysis for criterion 2

| Item | Sample or probe | Observed exit | Basis for "not absent" |
|---|---|---|---|
| Version control | `git rev-parse --is-inside-work-tree` | 0, prints `true` | Probe |
| `.env` files | `.env`, `.env.local` | 0 each | Probe, path strings only |
| `.env.example` | `.env.example` | 1 | Probe. Kept by the `!.env.example` rule |
| Personal settings | `.claude/settings.local.json` | 0 | Probe, path string only |
| `.checks` outputs | `.checks/x` | 0 | Probe |
| Caches with a rule | `.venv/x`, `node_modules/x`, `.next/x`, `scripts/__pycache__/a.pyc`, `.DS_Store` | 0 each | Probe |
| Disposable data | `infra/supabase/volumes/x`, `supabase/.temp/x`, `supabase/.branches/x`, `x.log` | 0 each | Probe |
| Local transcripts | `transcript.jsonl`, `transcripts/x.md`, `.claude/projects/x.jsonl` | **1 each, no rule** | **User decision OQ-1 only, as recorded. Not a probe result** |
| Five cache categories | `.pytest_cache/x`, `.ruff_cache/x`, `.mypy_cache/x`, `x.tsbuildinfo`, `.pnpm-store/x` | **1 each, no rule** | **Coordinator scoping call only. No user decision** |
| Provider master-key file | Not probed | None | `PRD-Model-Providers.md` places it outside the repository, according to the inventory and proposal. I did not re-check that source passage |

Checks on what the scoping calls rely on:

- `PRD-Development-Harness.md` line 71 reads "Ignore `.claude/settings.local.json`, local transcripts, bulky `.checks` outputs, caches and disposable data". It does not limit "caches" to tools in use.
- `test -e` exits 1 for `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and `.pnpm-store`, and `find` lists no `*.tsbuildinfo` outside `.git` and `research/upstream`. None of them exists today.
- `.venv`, `node_modules`, `.next`, `package.json` and `pyproject.toml` also exit 1 under `test -e`. So "tools in use" does not explain which caches have rules, which agrees with review finding F-2.

**If either scoping call is overruled, this score should not stand.** With "required ignores are absent" read as "any required ignore", the Given holds on the probes. No rule was established, so that reading would point to the Then not being met. That would be a failure, not an unexercised scenario. I did not score it that way, because the recorded decision and the coordinator's call currently exclude that reading, and I make no determination that overrides them. The coordinator or user should decide it, not this report.

The Then clause's constraint is not contradicted by these filename checks. They show only that nothing bad turned up, not that this story established anything:

- The history filename scan lists only `research/qwen38-gguf-memory.jsonl`. The first record's field names are memory-sample fields; other records were not inspected.
- The untracked filename scan exits 1.
- The same filter over `.checks/US-1.1/changed.txt` exits 1 across its 10 paths.
- A credential or transcript under an unremarkable name would not appear in any of these.

No fixture was run. The plan (line 165) gives the reason: this story implements no establishing behavior, so a disposable repository would exercise only commands written for the test.

## Evidence Commands

Manifest comparison, first and last. Both results are reported under "Manifest comparison results".

```bash
python3.12 scripts/story_manifest.py compare US-1.1
"/Users/josoroma/sites/autobots/research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch" --project-root "/Users/josoroma/sites/autobots" doctor --json
"/Users/josoroma/sites/autobots/research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch" --project-root "/Users/josoroma/sites/autobots" workflow-status --change us-1-1-h0-repository-prerequisite-inventory --json
```

```text
PASS: compare: US-1.1: 10 files match the reviewed manifest   (exit 0)
doctor: every check PASS, none FAIL or UNSUPPORTED             (exit 0)
workflow-status: gate 5 review pass; first incomplete gate testing (exit 0)
```

Tool probes. Each ran by absolute path, and results are in the ignored `.checks/US-1.1/tester/tool-versions.txt`.

```bash
/usr/bin/git --version
/opt/homebrew/bin/python3.12 --version
/Users/josoroma/.local/bin/python3.12 --version
/opt/homebrew/bin/uv --version
/Users/josoroma/.local/bin/uv --version
/opt/homebrew/bin/node --version
/Users/josoroma/.nvm/versions/node/v22.23.2/bin/node --version
/Users/josoroma/.local/bin/node --version
/Users/josoroma/.nvm/versions/node/v22.13.1/bin/node --version
/opt/homebrew/bin/npm --version
/Users/josoroma/.nvm/versions/node/v22.23.2/bin/npm --version
/Users/josoroma/.local/bin/npm --version
/Users/josoroma/.nvm/versions/node/v22.13.1/bin/npm --version
/Users/josoroma/.nvm/versions/node/v22.23.2/bin/corepack --version
/Users/josoroma/.nvm/versions/node/v22.13.1/bin/corepack --version
/usr/local/bin/docker --version
/usr/local/bin/docker compose version
/usr/local/bin/docker-compose version
/Users/josoroma/.docker/cli-plugins/docker-compose version
/opt/homebrew/bin/supabase --version
/usr/bin/jq --version
/bin/bash --version
/Users/josoroma/.nvm/versions/node/v22.23.2/bin/openspec --version
/opt/homebrew/bin/claude --version
command -v pnpm
which -a pnpm
which -a git python3.12 uv node npm corepack docker docker-compose supabase jq bash openspec claude   # run per tool
ls /Users/josoroma/.nvm/versions/node/
alias python3
```

```text
All 24 version commands exit 0, with first-line output equal to the inventory's Version column:
git version 2.54.0 (Apple Git-157)
Python 3.12.16 and Python 3.12.9
uv 0.13.6 (Homebrew 2026-10-26 aarch64-apple-darwin) and uv 0.11.18 (e32666915 2026-06-01 aarch64-apple-darwin)
v26.13.0, v22.23.2, v22.22.3, v22.13.1
npm 11.20.0, 10.9.8, 10.9.8, 10.9.2
corepack 0.34.6, 0.30.0
Docker version 29.9.2, build a82e528
Docker Compose version v5.6.1 (three paths)
supabase 2.98.2
jq-1.7.1-apple
GNU bash, version 3.2.57(1)-release (arm64-apple-darwin26)
openspec 1.13.2
2.1.314 (Claude Code)

command -v pnpm       exit 1
which -a pnpm         exit 1, "pnpm not found"
python3 alias         /opt/homebrew/opt/python@3.12/bin/python3.12
/usr/bin/env python3  Python 3.15.2
/usr/bin/env node     v26.13.0
```

**`supabase --version` ran exactly once, as this task required, and appears to make an outbound update check (review finding F-1).** It printed `2.98.2`, exit 0, and wrote a notice naming v3.0.0 to standard error. I took no packet capture, so the outbound request is inferred from the reviewer's sandbox result and this notice.

Repository, assets and scans:

```bash
git rev-parse --is-inside-work-tree
git branch --show-current
git branch --format='%(refname:short)'
git remote
git log --oneline | wc -l
git ls-tree -r --name-only 34ae38f | awk -F/ '{print $1}' | sort | uniq -c
git ls-files | awk -F/ '{print $1}' | sort | uniq -c
test -e <each of the 19 recorded asset paths>
git log --format='%h' -- .gitignore
git check-ignore -q --no-index -- <each sample in the table above>
git log --all --name-only --format= | sort -u | grep -i -E '(^|/)\.env|\.key$|\.pem$|\.p12$|secret|credential|transcript|\.jsonl$|\.sqlite|\.db$|/volumes/|settings\.local'
git ls-files --others --exclude-standard | grep -i -E 'transcript|\.jsonl$'
grep -l -E 'sk-or-v1-[A-Za-z0-9]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|ghp_[A-Za-z0-9]{20,}' docs/engineering/prerequisite-inventory.md
git diff --quiet HEAD -- .gitignore .claude/settings.json docs/engineering/runbooks/development-harness.md scripts tests
git diff --quiet HEAD -- .gitignore
git status --short | diff .checks/US-1.1/status-before.txt -
research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch --project-root /Users/josoroma/sites/autobots check-scope --plan openspec/changes/us-1-1-h0-repository-prerequisite-inventory/implementation-plan.md --diff .checks/US-1.1/changed.txt
```

```text
is-inside-work-tree   true, exit 0
branch                delivery/epic-1; branches delivery/epic-1 and main
git remote            prints nothing, exit 0
commits               2
tracked files         159 at 34ae38f and under git ls-files; per-path counts equal the inventory
asset paths           19 of 19 test -e exit 0; tracked counts equal the inventory
.gitignore history    34ae38f, 5e46124
history scan          research/qwen38-gguf-memory.jsonl only, exit 0
untracked scan        exit 1, nothing listed
narrow secret scan    exit 1, nothing listed
wider secret scan     0 lines for each of 10 shapes: AWS key, GitHub token, Slack token, Google key, JWT, generic sk- key, secret-like assignment, URL credentials, git@ remote, any http(s) URL
git diff --quiet      exit 0 for both commands
status vs before      adds only docs/engineering/evidence/US-1.1/ and docs/engineering/prerequisite-inventory.md, plus files inside the already-listed change directory
check-scope           IN SCOPE, 10 changed, all predicted, exit 0
```

The plan's expected status difference was "limited to the inventory and the change directory". The evidence directory is also new. It holds the capture manifest, which the plan lists under coordinator-owned evidence, so this is not an unplanned path.

## DH-W05: runbook exercise

Procedure: "Run the delivered checks" in `docs/engineering/runbooks/development-harness.md`, plus its backlog validation command. The runbook was not edited.

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/specs.py validate
TMPDIR=/Users/josoroma/sites/autobots/.checks/US-1.1/tester/tmp PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/verify.py --profile harness
PYTHONDONTWRITEBYTECODE=1 python3.12 scripts/verify.py --profile db
```

| Step | Expected in runbook | Observed | Exit |
|---|---|---|---|
| `specs.py validate` | Success when structure and navigation match | `PASS: validate: 10 epics, 42 stories, 86 tasks` | 0 |
| `verify.py --profile harness` | Configuration, backlog validation and nonempty tests pass with unchanged input fingerprints | Status `passed`, `inputs_stable` true, 3 checks passed. Standard error empty | 0 |
| Inspect `.checks/harness/latest.json` | Actual commands, counts and output, no live model qualification | `template` false, `inputs_unchanged_during_check` true, model transport `none` on all checks, `Ran 69 tests`, `OK`, Python 3.12.16, 74 inputs, `not_tested` lists Claude event delivery, application, Supabase, Docker, OpenRouter inference and complete H0/H1 | Not a command |
| `verify.py --profile db` | Exit 2 with `not_implemented`; no containers or database | `{"profile": "db", "status": "not_implemented", ...}`. Source lines 51-55 return before any other work | 2 |

- Harness `input_fingerprint`: `faa0903cbddc5befdbe87c7fad3e449728e34a46214713e9ada872403b2cdae9`. This is `verify.py`'s own fingerprint, computed over a different file set from the reviewed manifest, so the two values are not expected to be equal.
- `verify.lock` is absent after the runs (`test -e` exit 1).
- **Two environment settings differ from the runbook's literal command.** `TMPDIR` keeps the test fixtures inside the project, because this task forbids creating files outside it. It points to an ignored directory that held 0 entries afterward. `PYTHONDONTWRITEBYTECODE=1`, set on all three commands, avoids new bytecode. So the runbook's default temporary location was not exercised.
- **Write outside `.checks/US-1.1/`.** The harness command replaced the ignored `.checks/harness/latest.json`, as the runbook's procedure requires. Afterward, `find` listed no file under `scripts` or `tests/harness` newer than `.checks/US-1.1/changed.txt`, and bytecode times there all predate this run. The directory `.checks/US-1.1/tester/` holds this test's ignored output.
- **Plan and runbook differ on one point.** Plan line 172 says `--profile db` is not part of this story, while the runbook's procedure includes it. I ran it because this task names the procedure. It is a checked limitation, not database acceptance.
- **Not exercised:** `render`, "Inspect or use the assistant integration", actual assistant event delivery, and the failure and recovery table. A passing harness run says nothing about the inventory's accuracy and is harness evidence only.

## Observations, not scored as failures

- **F-1 still stands.** Inventory line 128 records only a notice, and lines 227-229 give no network warning. Disposition is in the work item.
- **F-2 and F-3 still stand.** Line 180 says "tools in use" for tools that are absent. Line 140 says "`CODEBASE.md` was not edited", while `git diff` shows 3 added and 3 removed lines there. Neither changes a recorded path, version or missing prerequisite.
- **New, minor.** Inventory line 85 says install paths come from `which -a`, but `which -a docker-compose` lists only `/usr/local/bin/docker-compose`. The recorded `/Users/josoroma/.docker/cli-plugins/docker-compose` exists and returned the recorded version, so the value is accurate and only its stated source is loose.
- **Archive condition, for the coordinator.** The bridge's unmet-Given exception (`.claude/rules/ohmyorch-delivery.md` line 71) requires that "re-run probes evidence" the Given does not hold. They do for version control and concrete-path ignores. **They do not for local transcripts or the five caches.** The work item names the scenario as unexercised. The evidence summary does not exist yet.

## Failures

None. No criterion was scored as failing. Criterion 2 is `UNVERIFIED`, which is neither a pass nor a failure.

## What could not be checked

- **Whether the user made the recorded decisions.** I saw OQ-1 and the unmet-Given exception only in the project records and this task's computed text. The user's relayed request in this run does not state them.
- **The outbound request itself,** and whether any other version probe contacts the network. Only inference for `supabase`; nothing tested for the others.
- **Whether the probed tools wrote their own caches or logs under the home directory.** The plan allows that they may. I did not scan the home directory, so I cannot state that this run created nothing outside the project.
- **Secrets outside the scanned shapes,** and the mechanical absence of the master-key filename.
- **Non-overwrite of `.claude/settings.local.json`,** and the implementer's process claims that leave no artifact.
- **Installs outside the search path,** apart from the Corepack path noted above.
- **Deliberately left alone:** `.env` files, the provider master-key file, the contents of `.claude/settings.local.json`, the environment, `PATH`, remote URLs, `docker version`, `docker info`, the Docker engine, installs and service starts.
- **Not re-run:** `openspec validate --strict` and `openspec list`. Neither is in this task's list or the plan's Test Strategy, and `workflow-status` supplied the gate state.

No project hook denied any command, so nothing was left out or rephrased for that reason.

## Manifest comparison results

- First, before any probe: `PASS: compare: US-1.1: 10 files match the reviewed manifest`, exit 0.
- During testing, after the runbook exercise: the same output, exit 0.
- Last, after this report was written and validated: the same output, exit 0. The only later edits to this report added this result, the validator result and the corrected environment note. The report is not in the manifest.

## Report validation

`ohmyorch validate-test-report --report openspec/changes/us-1-1-h0-repository-prerequisite-inventory/test-report.md --change us-1-1-h0-repository-prerequisite-inventory --story US-1.1` reported 0 failures and 1 warning (partial coverage, 1 of 2), exit 0.

`workflow-status` then reported gate 6 passing and `archiveEligible: true`. **That does not settle archive.** The upstream gate passes `UNVERIFIED` rows, and the bridge rule states it is necessary but not sufficient.

## Handoff

To the coordinator, for the evidence review and then the `archive` decision. No product file was changed by this test. This report does not declare the story delivered or accepted.

Before `archive`, the coordinator needs to resolve the following:

1. **Five cache categories.** These rest on a coordinator scoping call with no user decision. The user should confirm or overrule it, since overruling it changes criterion 2.
2. **Exception wording.** Decide whether the bridge's "re-run probes evidence that" condition can be met for local transcripts and the five caches, given that the probes there show no rule. Review open question 1 on the "disposable environment" sentence also needs a ruling from the user; the coordinator has answered it, but no user decision is recorded.
3. **Records.** The evidence summary must name this scenario as unexercised. Any report of US-1.1 should say the same.
