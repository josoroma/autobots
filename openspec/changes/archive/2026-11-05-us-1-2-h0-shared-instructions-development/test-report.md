# Test Report — us-1-2-h0-shared-instructions-development

Change: us-1-2-h0-shared-instructions-development
Story: US-1.2
Verdict: pass
Coverage: 3/3 acceptance criteria evaluated
Reviewed fingerprint: 88121c61d7a9bf19371dae19b8893624865c2438c2170323be84fa05cf97f51b

Tester: `ohmyorch:tester`, a delegated context separate from the implementer, reviewer and coordinator. Run on 2026-11-05 on branch `delivery/epic-1`, base revision `9714930`, with the reviewed uncommitted tree. Harness `input_fingerprint`: `7e00bc4fe16a9ff1461b924f9c2de73bbf46a19db2e29704bf24d1f999606bf3`. No product code or test was changed. Application model transport was `none` throughout.

This is harness evidence only. It establishes neither H0, H1 nor product acceptance.

## Acceptance Criteria Evaluated

| # | Scenario | Result | Evidence |
|---|---|---|---|
| 1 | Keep development policy portable | PASS | **Observed, mechanical:** 53 asset tests OK, 122 harness tests OK, `project_configuration` errors `[]`, 8 rule files carry an allowed link. On a scratch copy of the real text, removing a rule's check section, an `AGENTS.md` row, or adding an unmapped heading each produced exactly one named error. **Observed, by my reading:** each rule link fits its DH-09 profile; `AGENTS.md` has a row for all 5 rule sources plus settings and `CLAUDE.md`; all 12 common-rule rows show no contradiction among authored assets; all 13 skills and 7 agents hold the DH-04 elements. `CLAUDE.md` diff is outside the managed block. **CLI:** on final-tree copies with 2.1.314 the plugin-shaped `--strict` pair discriminates; the `.claude` pair does not. **Recorded decisions, not observed:** one link per rule file (decision 1); the runbook-exercise row rests on the coordinator's reading (decision 8), and its condition, that the summary states revision, date and result, cannot be observed yet because the summary does not exist. Links name future profiles, so review is what applies today |
| 2 | Separate optional assistant activation | PASS | **The Given was arranged, not naturally present: no real adapter was inactive on this machine.** Real state is `configured_unqualified` / `delivery_unverified`, 2.1.314, `model_route: not_checked`. **Observed, arranged unavailable:** `PATH=/usr/bin:/bin` finds no `claude`; verifier exit 0, `passed`, `inactive` / `unavailable`, `not_tested` lists Claude event delivery. **Observed, arranged incompatible:** stub at 2.1.200 gives exit 0, `inactive` / `version_below_minimum`, record holds only `--version`. Invalid configuration on a scratch root gives `inactive` / `configuration_invalid` or `minimum_unknown`. **Observed, nothing introduced:** provider and `claude -p` scans have no hit; unchanged-path `git diff --quiet` block exit 0; both qualification literals unchanged; `not_tested_but_active` refused; added text read, nothing claims activation. **Recorded decisions, not observed:** scoring an arranged Given rests on the 2026-11-05 clause in bridge line 75 and Decision 0002, which I read as recorded and did not hear from the user; "incompatible" covering presence, version and configuration is decision 3, and the model route is not checked |
| 3 | Ingest without inventing product behavior | PASS | **The Given was arranged on a synthetic fixture; nothing here concerns the real PRDs.** **Observed, on the one run's output:** `render` and `validate` exit 0, 5 stories. Before-to-after diff has zero removed lines, and adds only US-1.5 and navigation. Statuses match the expected result fixed before the run. SP diffs empty. Deps diff adds only `US-1.5: - US-1.2`. Second render unchanged. Stale copy fails, then recovers. No `DONE`, no ticked task, other sources unchanged. `apps` and `services` absent, and real `SPECS.md` hash equals the recorded one. Negative controls show the validator rejects a bad source anchor, missing Given and a premature `READY`. **Observed, by my reading:** each scenario traces to a cited source, seven retries is not a requirement, and the summary claims no delivery and says validation was not executed. **Not observed:** the delegation and the coordinator's persistence, for which I have only the artifacts. The ingestor's loaded definition is unproven. **Recorded decision:** coordinator as paired caller and tester running `render` and `validate` (decision 5). One run shows one output, not that the ingestor is reliable |

## Evidence Commands

All commands ran from the repository root in zsh. Raw output is in ignored `.checks/US-1.2/test/` and `.checks/US-1.2/forward/`.

### Bound inputs

```bash
python3.12 scripts/story_manifest.py compare US-1.2      # first
research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch --project-root /Users/josoroma/sites/autobots doctor --json
research/upstream/OhMyOrch/plugins/ohmyorch/bin/ohmyorch --project-root /Users/josoroma/sites/autobots workflow-status --change us-1-2-h0-shared-instructions-development --json
diff <(sort .checks/US-1.2/changed.txt) <(jq -r '.files|keys[]' docs/engineering/evidence/US-1.2/reviewed-manifest.json | sort)
```

```text
PASS: compare: US-1.2: 34 files match the reviewed manifest      exit 0
doctor: every check PASS, exit 0
workflow-status: gate review pass, first incomplete gate testing, tasks 18/18
changed.txt against manifest keys: no difference, exit 0
manifest fingerprint: 88121c61d7a9bf19371dae19b8893624865c2438c2170323be84fa05cf97f51b
git status paths outside changed.txt: only the records docs/engineering/evidence/US-1.2/, docs/engineering/work-items/US-1.2.md, openspec/delivery/goal.md and the change directory
```

### Scenario 1: Keep development policy portable

```bash
PYTHONDONTWRITEBYTECODE=1 python3.12 -m unittest discover -s tests/harness -p 'test_assistant_assets.py' -v
python3.12 scripts/specs.py validate
python3.12 scripts/verify.py --profile harness
jq '.checks[0].errors' .checks/harness/latest.json
for p in $(jq -r '.verification.pending_profiles[]' .claude/autobots.json); do python3.12 scripts/verify.py --profile "$p"; done
git diff HEAD -- CLAUDE.md
git -C research/upstream/OhMyOrch rev-parse HEAD
shasum -a 256 research/upstream/OhMyOrch/plugins/ohmyorch/agents/spec-ingestor.md
claude --version
claude plugin validate --json .checks/US-1.2/test/cli/claude-good            # and claude-broken
claude plugin validate --strict --json .checks/US-1.2/test/cli/plugin-good   # and plugin-broken
```

```text
Ran 53 tests in 3.688s, OK, exit 0, no skips or failures
PASS: validate: 10 epics, 42 stories, 86 tasks, exit 0
harness: status passed, inputs_stable true, three checks passed, Ran 122 tests, exit 0
project_configuration errors: []
fast, full, db, operations: exit 2, not_implemented, each
CLAUDE.md diff: one changed line, the runbook link, outside the OHMYORCH block
pin: fddfbf53c8c10d45782796cc9a7edf95bc8d3a07 in the checkout, upstream.commit, the install SHA, CODEBASE.md, the page, the skill and the ingestor
source hash: 091932c9408125f9b54e9748bc7f443ff11cd3033ad2ded0f7baa1a60bbcaa5d, equal to the page
2.1.314 (Claude Code)
```

Syntax, CLI, on new copies taken from the final tree. `diff -r` showed the copies equal the tree, and each broken copy differs from its good copy only by the `description` line removed from `skills/autobots-python/SKILL.md`.

| Pair | Good copy | Broken copy | Counts |
|---|---|---|---|
| `.claude` shape, `--json` | exit 0, `success: true`, empty `contents` | exit 0, `success: true`, warning on `description` | No |
| Plugin shape, `--strict --json` | exit 0, `success: true`, empty `contents` | exit 1, `success: false`, warning on `description` for that skill, `errors` empty | Yes, on the page's reading that `--strict` turns the warning into the failure |

This also closes review finding F-4's rerun: both pairs ran on the final tree. It discriminates one skill fault only; agents appear only in the good copies, and rules are not covered by the CLI.

Scratch probe on the real text, `.checks/US-1.2/test/mut-2`, copied by name, with the mapped documents as empty placeholders, calling `config_errors` and `adapter_status` with a compatible stub. A first attempt, `mut-1`, lacked the mapped documents, so every case already had errors. I discarded its adapter results.

| Change to the copy | `config_errors` | Adapter |
|---|---|---|
| None | `[]` | `configured_unqualified` / `delivery_unverified` |
| `nextjs.md` loses its check section | One error naming the file | `inactive` / `configuration_invalid` |
| `AGENTS.md` loses the Work protocol row | One error naming the row | `inactive` / `configuration_invalid` |
| `AGENTS.md` gains an unmapped heading | One error naming the heading | `inactive` / `configuration_invalid` |

Common rules, compared by reading the copies on the final tree, not from the persisted table:

| Common rule | Consistent | Basis |
|---|---|---|
| Profile availability | yes | `AGENTS.md`, `delivery.md`, verify skill, `autobots.json`, `README.md` and the runbook agree, and I observed exit 2 for all four |
| Interpreter | yes | `AGENTS.md` and runbook `python3.12`, settings and runbook's reduced-`PATH` commands the absolute path. Source discrepancy, reported and not edited: `PRD-Development-Harness.md` line 123 says `python3` |
| OpenRouter-only | yes | `AGENTS.md`, gateway rule and skill, `CLAUDE.md` |
| No automatic actions in hooks | yes | `AGENTS.md`, `delivery.md`, docker skill. `dispatch.py` has no subprocess call and imports only `report_state`, which does not probe |
| Review independence and record ownership | yes | `ohmyorch:reviewer` writes a verdict and `autobots-reviewer` is read-only: two named roles, bridge line 7 and Decision 0002. `delivery.md`'s "read-only" is the closest reading, and it routes loop delivery to the bridge |
| Document map | yes | `autobots.json` and `project.json` agree on specs, codebase and product, and a test covers it |
| Upstream pin | yes | Same commit in every copy above |
| Plugin stance | yes | Decision 0002 supersedes only 0001's plugin clause, and 0001 and the page's banner both say so. `CLAUDE.md`'s sentence is about what hooks do |
| Ingestion ownership | yes | `CLAUDE.md`, skill, agent. The runbook states the `render` and `validate` split as specific to the exercise |
| Story field order | yes | The ingestor names `Change:` below `Status:`, a test passes, and the run's output follows it |
| Evidence locations | yes | `AGENTS.md`, `delivery.md`, both skills, DH-09.2 |
| Runbook exercise status | yes as text, condition open | Contract line 70, the bridge's Records row, the runbook and DH-W05 do not contradict each other. See Limits for SP-018 and the summary |

DH-04: I read all 13 skills and 7 agents, and the table in `docs/engineering/evidence/US-1.2/dh-04-table.md` holds on my reading, one row per file. The thin cells are the ones the reviewer named: `autobots-plan-change` failure behavior and `autobots-reviewer` result contract. Only the tool-set test is mechanical.

### Scenario 2: Separate optional assistant activation

```bash
PATH=/usr/bin:/bin /bin/sh -c 'command -v claude'
PATH=/usr/bin:/bin /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter, .not_tested' .checks/harness/latest.json

STUB="$PWD/.checks/US-1.2/stub"
# the runbook's stub commands, as written
PATH="$STUB:/usr/bin:/bin" /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter' .checks/harness/latest.json
/bin/cat "$STUB/args"

python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter, .not_tested' .checks/harness/latest.json

git diff --quiet HEAD -- .claude/settings.json .claude/autobots.json .claude/hooks/dispatch.py .claude/rules/delivery.md .gitignore .claude/skills/autobots-nextjs/SKILL.md .claude/skills/autobots-plan-change/SKILL.md .claude/skills/autobots-runbook-evidence/SKILL.md .claude/skills/autobots-spec-ingest/SKILL.md .claude/skills/autobots-supabase/SKILL.md .claude/skills/autobots-verify-change/SKILL.md .claude/agents/autobots-database.md .claude/agents/autobots-infrastructure.md .claude/agents/autobots-python-worker.md .claude/agents/autobots-reviewer.md
git diff HEAD -- scripts .claude/hooks tests/harness | grep -E '^\+' | grep -inE 'anthropic|ollama|litellm|openai|bedrock|vertex|gemini|claude[[:space:]]+(-p|--print)|--print\b'
grep -inE 'anthropic|ollama|litellm|openai|bedrock|vertex|gemini|claude[[:space:]]+(-p|--print)|--print\b' tests/harness/test_assistant_assets.py tests/harness/forward_arrangement.py
jq '.assistant, .upstream.delivery_plugin' .claude/autobots.json
```

```text
command -v claude under the reduced PATH: exit 1
unavailable: verifier exit 0, "passed", {"state":"inactive","reason":"unavailable","minimum_version":"2.1.295","model_route":"not_checked"}
             not_tested: Claude event delivery, application, Supabase, Docker, OpenRouter inference, complete H0/H1
incompatible: verifier exit 0, "passed", {"state":"inactive","reason":"version_below_minimum","minimum_version":"2.1.295","model_route":"not_checked","observed_version":"2.1.200"}
stub record: --version (one line)
real: verifier exit 0, "passed", {"state":"configured_unqualified","reason":"delivery_unverified","minimum_version":"2.1.295","model_route":"not_checked","observed_version":"2.1.314"}
both reports printed state and reason in the summary
unchanged-path block: exit 0
scans: no hit, grep exit 1 each; baseline git grep of provider names in scripts, .claude/hooks and tests/harness: no hit
assistant.event_delivery_qualification: not_tested
upstream.delivery_plugin.event_delivery_qualification: not_qualified_one_pretooluse_event_observed
assistant.model_configuration: unchanged
```

| Scratch configuration, `mut-2`, compatible stub | `config_errors` | Adapter |
|---|---|---|
| `assistant` qualification `not_tested_but_active` | Refused, one error | `inactive` / `configuration_invalid` |
| Plugin qualification `qualified` | Refused, one error | `inactive` / `configuration_invalid` |
| `env` or `model` key in settings | Refused, one error each | `inactive` / `configuration_invalid` |
| Minimum version `abc` | Refused, one error | `inactive` / `minimum_unknown` |

Failing, hanging and unparsable versions, 2.1.99, 2.1.295 and 2.1.1000 rest on the passing adapter unit tests with stubs, not on a separate run here.

Wording: I read the added lines of `AGENTS.md`, `CLAUDE.md`, rules, skills, agents, the runbook and the adaptation page that matched `qualified`, `activated`, `active`, `event delivery`, `proven` or `delivered`. Every hit is a denial, a limit, the two state names or the plugin's install history. None says the hooks, plugin or adapter are qualified, or that event delivery is proven. A keyword filter can miss other phrasing.

### Scenario 3: Ingest without inventing product behavior

The runbook's two tester blocks ran as written with `F=.checks/US-1.2/forward`. I did not repeat `R`, `B` and the other variables here.

```bash
python3.12 scripts/specs.py render --project-root "$R" --path SPECS.md
python3.12 scripts/specs.py validate --project-root "$R" --path SPECS.md
shasum -a 256 -c "$F/delegation.sha256"
test "$(jq -r --arg p "$INGESTOR" '.files[$p]' "$MANIFEST")" = "$(awk -v p="$INGESTOR" '$2 == p {print $1}' "$F/delegation.sha256")"
git diff --quiet HEAD -- "$SKILL"
test "$(git show "HEAD:$SKILL" | shasum -a 256 | awk '{print $1}')" = "$(awk -v p="$SKILL" '$2 == p {print $1}' "$F/delegation.sha256")"
diff <(grep -E '^(# EPIC-|### US-)' "$B/SPECS.md") <(grep -E '^(# EPIC-|### US-)' "$R/SPECS.md")
diff <(grep -E '^\| \[SP-' "$B/SPECS.md") <(grep -E '^\| \[SP-' "$R/SPECS.md")
diff <(grep -oE 'SP-[0-9]+' "$B/SPECS.md" | sort -u) <(grep -oE 'SP-[0-9]+' "$R/SPECS.md" | sort -u)
diff "$F/deps-before.txt" "$F/deps-run.txt"
awk '/^### US-/{id=$2} /^(Status|Change):/{print id, $0}' "$R/SPECS.md"
```

```text
PASS: render: 1 epics, 5 stories, 16 tasks, exit 0
PASS: validate: 1 epics, 5 stories, 16 tasks, exit 0
.claude/agents/autobots-spec-ingestor.md: OK
.claude/skills/autobots-spec-ingest/SKILL.md: OK, exit 0
ingestor hash at delegation equals the manifest entry e471df5a..., exit 0
skill unchanged from HEAD, exit 0; hash at delegation equals HEAD's blob 96ed8eda..., exit 0
headings diff: > ### US-1.5: Save the composer draft automatically
SP rows diff: none, exit 0
SP ids diff: none, exit 0
deps diff: > US-1.5: - US-1.2
US-1.1: Status: READY
US-1.2: Status: IN PROGRESS
US-1.2: Change: `openspec/changes/fixture-us-1-2/`
US-1.3: Status: NEEDS CLARIFICATION
US-1.4: Status: BLOCKED
US-1.5: Status: BLOCKED
```

```bash
python3.12 scripts/specs.py validate --project-root "$B" --path SPECS.md
grep -c '^## SP-' "$B/CONTRACT.md"
grep -c 'When the composer draft changes' "$B/PRD.md"
grep -F 'US-1.3: - US-1.2' "$F/deps-before.txt"
python3.12 tests/harness/forward_arrangement.py "$F/rerun"
diff -r "$B" "$F/rerun"
shasum -a 256 "$R/SPECS.md" > "$F/rendered.sha256"
python3.12 scripts/specs.py render --project-root "$R" --path SPECS.md
shasum -a 256 -c "$F/rendered.sha256"
cp -R "$R" "$F/stale"
sed -i '' 's/^Status: READY$/Status: BLOCKED/' "$F/stale/SPECS.md"
python3.12 scripts/specs.py validate --project-root "$F/stale" --path SPECS.md
python3.12 scripts/specs.py render --project-root "$F/stale" --path SPECS.md
python3.12 scripts/specs.py validate --project-root "$F/stale" --path SPECS.md
grep -c '^Status: DONE' "$R/SPECS.md"
grep -c '^- \[[xX]\]' "$R/SPECS.md"
diff -r -x SPECS.md "$B" "$R"
```

```text
PASS: validate: 1 epics, 4 stories, 13 tasks, exit 0
2
1
US-1.3: - US-1.2
arrangement rerun exit 0; diff against before/: none, exit 0
second render: run-1/SPECS.md: OK, exit 0
stale: FAIL: line 1: navigation is missing or stale; run scripts/specs.py render, exit 1
stale render: PASS, exit 0; stale validate: PASS, exit 0
DONE count 0, exit 1; ticked count 0, exit 1, which the runbook expects
diff -r -x SPECS.md: none, exit 0
```

Further checks from the plan's table, and controls I added:

```text
Title: "# Autobots Fixture Specifications" in before/SPECS.md, run-1/SPECS.md and the retained fixture
Full diff before/ to rendered run-1: zero removed lines
Persisted file before my render against raw-response.md: exact prefix; raw equals document plus summary
Persisted against rendered: only US-1.5 navigation lines added, including the US_1_2 -.-> US_1_5 edge
Retained fixture validate: PASS, 1 epics, 4 stories, 13 tasks, exit 0
SPECS.md hash: 269eb9aa..., equal to .checks/US-1.2/specs-before.sha256; git diff shows only the coordinator's status lines and Change line
grep of the real SPECS.md for the fixture's Change path, the new story's title or REQ-06: 0
test ! -e apps, test ! -e services: exit 0 each
Arrangement on an existing destination: ERROR: destination already exists, exit 2
Negative controls on copies of the output, .checks/US-1.2/test/neg-1:
  source anchor changed: FAIL: line 265: source heading/HTML id '#req-06-not-there' does not exist in PRD.md, exit 1
  Given removed: FAIL: line 270: Scenario ... requires ordered Given, When, Then, exit 1
  US-1.5 set READY: FAIL: line 256: US-1.5 READY requires all dependencies DONE and no unresolved External dependency, exit 1
  US-1.1 set DONE: FAIL: line 118: US-1.1 is DONE with unfinished tasks, exit 1
```

Forward result against the expected result fixed in the runbook: **no difference.** US-1.5 is in EPIC-1, takes the next free ID, cites `PRD.md#req-06-composer-autosave`, has `Dependencies: - US-1.2` and `Status: BLOCKED`.

Reading, by inspection, because entailment is not mechanically decidable:

- **US-1.5:** autosave on change, local storage and the delivery precondition all come from REQ-06, and REQ-06 itself points to REQ-02. It also cites REQ-02. The fixed expected result names only REQ-06, and this addition does not contradict it. I record it rather than treat it as a difference.
- **Stories US-1.1 to US-1.4:** byte-identical to `before/`. US-1.1's "When the owner attempts to submit the draft" is not literally in REQ-01, which states the missing key and "do not dispatch". It is retained fixture text, not added by this run, and it adds no requirement beyond framing the dispatch REQ-01 forbids.
- **Seven retries:** appears only as descriptive context that denies being a limit, and US-1.3 stays `NEEDS CLARIFICATION` with the count as an open question.
- **REQ-04 and REQ-05:** both scenarios stay visible and US-1.4 stays `BLOCKED`.
- **`ingestion-summary.md`:** "Validation: not executed", no delivery claim, says it does not promote stories. It flags the fixture's unsupported `Change:` path and undelivered US-1.2 for the coordinator instead of changing them.
- **`design` key:** the copy's map has none, as the runbook expects. The agent's summary does not mention it. It changes nothing, and it is recorded here.

### Results by DH-09.2 class

| Class | Checks |
|---|---|
| `static` | `project_configuration`, rule, mapping and DH-04 reading, common rules, scans, unchanged-path block, hash bindings, values |
| `mock` | Stub at 2.1.200, adapter unit tests with stubs |
| `disposable` | Asset tests and scratch probes, CLI pairs on copies, arranged `PATH` run, the whole forward exercise. The report's `static_or_fixture` label maps here, as the plan says |
| `live` | Only the real CLI's `claude --version` and `claude plugin validate` output, which qualifies nothing. No live event delivery |

## Runbook Exercise (DH-W05)

Procedure: `docs/engineering/runbooks/development-harness.md`, exercised 2026-11-05 on base `9714930` plus the reviewed tree. The runbook itself was not edited. `grep -c 'Last exercised'` prints 0.

| Step | Run by | Result |
|---|---|---|
| Validate the backlog | Tester | As expected |
| `render` then `validate` on the real `SPECS.md` | Not run: no authorized backlog edit. Exercised on the copies | Render preserves authored content on the copy |
| Run the delivered checks, `--profile db` | Tester | Exit 0; exit 2 with `not_implemented` |
| Read the adapter status, real state | Tester | `configured_unqualified` |
| Arrange unavailable, as written | Tester | As expected |
| Arrange incompatible, as written | Tester | As expected. I also ran it once in a new directory, `.checks/US-1.2/test/stub-1`, with the same result |
| Final normal `verify.py` | Tester | Exit 0, ran after every arranged run |
| Forward steps 1 to 4: arrangement, hashes, delegation, verbatim persistence | Coordinator. I did not observe them, and checked only the artifacts | Artifacts consistent with the steps |
| Forward tester blocks, as written | Tester | Every expected result observed |
| Stale navigation failure and recovery | Tester, on a copy | Exit 1, then exit 0 and exit 0 |
| Recovery row, arrangement refuses its destination | Tester | Exit 2 |
| Recovery row, `jq '.checks[0].errors'` | Tester | `[]` |
| Recovery rows `minimum_unknown`, `configuration_invalid` | Tester, helper on a scratch root, not a full verifier run | As the table says |
| Recovery row `version_unknown` | Unit tests only | Not exercised as a full run |
| `verify.lock`, completion hook block, secret or destructive denial | Not exercised | Unverified by this run |
| Live assistant session: rules loaded, event delivery | Not exercised | Stays **configured, event delivery unverified** |

## Limits

These are limits on what the passes show, and none makes a criterion false.

- **Arranged conditions.** Scenario 2's inactive results come from a process-scoped `PATH`, a stub and scratch configuration. No real adapter was inactive on this machine, and these runs do not show how a real unavailable client behaves.
- **Stale plan text, per the coordinator's correction.** Plan lines 35, 255 and 440 and proposal lines 59 and 92 say Decision 2 rests on an unconfirmed sentence and that no decision was the user's. They are out of date, and I did not score under them. I scored under bridge line 75 and Decision 0002. I could not see the user's own words, and the coordinator's note is not a user statement, so this is reported as recorded. If that record were wrong, scenario 2's score would change and its observations and the code would not.
- **Decisions still the coordinator's and open to the user:** 1, 3, 4, 5, 6, 7 and 8. Decision 4's fallback did not apply, because one CLI pair counted on the page's reading. If that reading is rejected, DH-04's "qualified CLI" clause is not met.
- **SP-018 and the summary.** SP-018 says each runbook should "Record its last successful exercise and link evidence", and the runbook states these are recorded in the story's evidence and not in the runbook. That is decision 8, the coordinator's reading. The authored copies agree, so it is reported as a departure from a source's literal wording, which needs the user's confirmation. `docs/engineering/evidence/US-1.2/summary.md` does not exist yet, so the runbook's link to it does not resolve today. The evidence review must confirm that it states revision, date and result and lists the untested steps above. Otherwise that common-rules row reads `no`.
- **Ingestor.** The hash covers only the file on disk. The ingestor's definition actually loaded in the session that ran it is unproven, because the coordinating session started before the edit. I did not see the delegation prompt. That `raw-response.md` is the literal response rests on the coordinator's report: I confirmed only its internal agreement with the persisted document and summary. Read-only behavior rests on the frontmatter and on the unchanged sources afterward.
- **One run** shows one output, not that the ingestor is reliable. Synthetic `SP-*` sections show coverage survived on this fixture, not that real SP coverage would.
- **Delegation.** The forward exercise's one delegation used the developer assistant, as the runbook states, and was not application inference. Its route and cost were not observed. The developer client's model route is not checked anywhere.
- **Adapter field.** One observation across project and plugin hooks, from the project file only. `configured_unqualified` must not be read as compatible. Whether `claude --version` or `claude plugin validate` reaches the network is unknown.
- **Links.** Link presence does not make a rule's check exist. Four of the profiles rules link to exit 2 today.
- **Reported, not acted on:** the `python3` source discrepancy above. Also `README.md` still links HARNESS-ADAPT-001 as "Evidence", as the work item reports.
- **Review findings F-1 to F-3** are records for the coordinator and were not checked further here.

Not denied, not skipped: no project hook denied any command. One of my compound commands stopped on a zsh parse of an `echo` separator, and I reran it with a different separator. I ran no `supabase`, `docker` or `claude -p` command, no install and no service start, and read no secret file. `~/.claude/plugins/installed_plugins.json` was read only through a `jq` filter on this plugin's entry. The harness and asset test suites create and remove their own temporary directories, which per review may include the system temporary location; I did not confirm that for this run. Everything else I wrote is under `.checks/`, including `.checks/harness/latest.json` from the runbook's commands, and this report.

Last comparison, after this report was written. `test-report.md` is a record that `is_record` excludes, so this line does not disturb it:

```text
python3.12 scripts/story_manifest.py compare US-1.2
PASS: compare: US-1.2: 34 files match the reviewed manifest      exit 0
```

`validate-test-report` on this report: 0 failures, 0 warnings, exit 0.

## Failures

None.

## Handoff

Change eligible for the coordinator's evidence summary and work-item records, then the `autobots-reviewer` evidence review, then the completion gate and the bridge's `archive` conditions. No implementer work is needed. Acceptance alone does not archive the change, and no H0, H1 or product acceptance is claimed.
