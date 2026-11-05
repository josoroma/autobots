# Runbook: local specification and development harness

## Scope and prerequisites

Run from the Autobots workspace on this Mac with Python 3.12 or later. The hook interpreter is explicitly /opt/homebrew/bin/python3.12 (observed 3.12.16). If python3.12 is absent from PATH, use that absolute path. Plain python3 can resolve to macOS 3.9.6 in another process; unsupported versions fail clearly. Application dependency qualification remains separate; the pinned Node and Python environments have their own procedure in [the toolchains runbook](toolchains.md), and nothing here needs them. No package installation, API key, application model call, Docker or Supabase is needed for these commands; `jq` reads the report, and the forward procedure's one delegation step uses the developer assistant. Read the mapped sources in `.claude/autobots.json` and `CODEBASE.md` before changing the backlog.

This runbook covers the implemented `harness`, `fast` and `full` profiles. `db` and `operations` remain unimplemented and must return a nonzero unavailable result, not substitute a smaller passing suite. H0/H1 has additional pending requirements.

## Validate the backlog

```sh
python3.12 scripts/specs.py validate
```

Expected: success only when required fields, source locations, Gherkin scenarios, dependency/status rules and generated navigation match the authored stories. This checks structure and traceability locations; it does not certify semantic source agreement or implemented application behavior.

When an authorized story edit makes navigation stale, regenerate only the derived views:

```sh
python3.12 scripts/specs.py render
python3.12 scripts/specs.py validate
```

The renderer must preserve Product Context and all authored story content, IDs, statuses and task checkboxes. A second render should make no change. Invalid source stories must be repaired from evidence, not rewritten merely to satisfy the validator. Missing product behavior stays NEEDS CLARIFICATION; unresolved dependencies/conflicts stay BLOCKED.

## Run the delivered checks

```sh
python3.12 scripts/verify.py --profile harness
```

Expected: project configuration, backlog validation and nonempty behavioral tests pass with unchanged input fingerprints. Inspect `.checks/harness/latest.json` for actual commands, counts and output. Inputs edited during a check invalidate the result. The report excludes secret files and records no live model qualification.

```sh
python3.12 scripts/verify.py --profile db
```

Expected today: exit code 2 with `not_implemented`. It must not start containers or touch a database. This is a checked limitation, not database acceptance.

### Run the application profiles

`fast` and `full` need the prepared environments from [the toolchains runbook](toolchains.md). They never install, download or start a service, and their children get no inherited credential.

```sh
python3.12 scripts/verify.py --profile fast
python3.12 scripts/verify.py --profile full
```

| Profile | Runs |
|---|---|
| `harness` | Configuration, backlog validation and the deterministic harness tests |
| `fast` | `harness`, plus the Python steps for `services/agent/`, the web steps for `apps/web/` and `packages/`, and both for shared or check-infrastructure paths such as locks, `contracts/` and `scripts/verify.py`. No build. Everything else is recorded `not_run`, so a documentation-only change needs no prepared environment |
| `full` | `harness`, plus every step, including `next build` and the fault qualification below |

| Exit | Report `status` | Meaning |
|---|---|---|
| 0 | `passed` | Every selected check passed and no input changed during the run |
| 1 | `failed` | A required check failed, the non-mutation guard saw a change, or an input changed. This outranks exit 2 |
| 2 | `error` | A prerequisite is unavailable, a check could not start or timed out, or another check holds `verify.lock` |

Reports are `.checks/<profile>/latest.json`. Each binds to a fingerprint of the harness files plus application sources, manifests and locks, but not environments, caches or build output. Any change to those inputs makes every profile's report stale. The `Stop` hook wants a current `fast` or `full` report when uncommitted application or shared paths exist, and otherwise accepts any current report.

Not run by any profile: generated contract drift, because no contract exists yet; browser fixtures, because none are configured; and `tests/toolchain`, whose copies bootstrap from registries.

## Qualify deliberate faults

```sh
python3.12 scripts/qualify_faults.py
jq '.status, [.cases[] | select(.status != "passed") | .id]' .checks/faults/latest.json
```

Expected: exit 0, one `PASS:` line per case, and an empty list. It runs the pinned tools on `tests/faults/`. A good fixture must pass, and a bad one must fail with its case's marker, so a crashed tool does not count as a detected fault. Exit 1 means a case did not behave as expected, and exit 2 that the prepared environments are missing. The `model_real_bad` case runs with a placeholder key, not a real one, and must hit the socket block.

Never fix or remove a bad fixture to make this pass. It shows these checkers catch these faults. It does not qualify the product's state machine, contract generation or model gateway, and establishes neither H1 nor product acceptance.

## Validate completion evidence

For a work item that a story's acceptance or the user asks to record under DH-W01–06, start from [the templates](../templates/) and the [evidence contract](../evidence/README.md). Routine OpenSpec delivery does not use this, by Decision 0003.

```sh
python3.12 scripts/evidence.py fingerprints
python3.12 scripts/evidence.py validate <work-item-id>
python3.12 scripts/evidence.py complete <work-item-id>
```

Expected: `validate` exits 0 with `PASS` only when the record, manifest, summary, review, runbook and fingerprints are consistent and current. Otherwise it exits 1 with one `FAIL:` line per problem, and `complete` leaves the status unchanged. An unusable id exits 2. A hand-written `Status: COMPLETE` is not trusted: `validate` still fails it.

A pass shows internally consistent, current evidence. It does not show that a recorded assertion was correct.

## Inspect or use the assistant integration

Project configuration is `.claude/settings.json`; the dispatcher is `.claude/hooks/dispatch.py`. The scripts use bounded stdin JSON and invoke no model. The observed Claude Code 2.1.314 is newer than the documented 2.1.295 minimum for blocking hook startup failures; version compatibility is not event-delivery proof.

In a separately qualified compatible assistant session, inspect the loaded project rules, skills, agents and hooks, then test actual event delivery on a disposable fixture. Keep the existing OpenRouter-only constraint; do not add provider credentials or assume product model IDs are supported by the CLI. Until that exercise is recorded, the adapter is **configured, event delivery unverified**. Use the portable runner directly in the meantime.

Invoke `autobots-spec-ingest` for backlog ingestion; the read-only agent proposes content, and its caller writes and validates it. Use the plan/implementation/review/verification/runbook skills for an authorized bounded work item. Do not use ingestion as permission to start product development.

### Hook dispatcher behavior

These are fixture-tested script behaviors in `tests/harness/test_hooks.py`, not proof of event delivery.

| Input | Behavior |
|---|---|
| Malformed or oversized JSON, an unsupported event or tool, or an internal error such as a missing `harness_lib` | Exit 2, empty stdout and one fixed stderr line. Input is never echoed |
| No complete input within 9 seconds, below the configured 10-second timeout | Exit 2, the same way. `AUTOBOTS_HOOK_DEADLINE_SECONDS` can only shorten this |
| An unusable `file_path`: missing, over 4096 bytes, containing NUL, or a symlink loop | `PreToolUse` denies; `PostToolUse` returns the generic diagnostic |
| A secret name, before or after symlink resolution | `PreToolUse` denies |
| A filename with spaces, Unicode or shell metacharacters | Treated as data, and passed only as one argument after `--` |
| An edited Python file under `services/agent/` | `PostToolUse` names the affected domains, checks syntax and runs the prepared `ruff` for at most 3 seconds, reporting a finding, a missing tool or a timeout without echoing its output |

### Read the adapter status

`scripts/verify.py` derives `assistant_adapter` each time it runs the harness profile. It is recorded in the report and its state and reason are printed in the summary.

```sh
python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter, .not_tested' .checks/harness/latest.json
```

The state is one of exactly two values, compared as whole values: `inactive` contains "active" and `configured_unqualified` contains "qualified", and neither means that. The first matching row wins.

| Observed | `state` | `reason` |
|---|---|---|
| `claude` not found on the process `PATH` | `inactive` | `unavailable` |
| Recorded minimum version absent or unparsable | `inactive` | `minimum_unknown` |
| `project_configuration` has any error | `inactive` | `configuration_invalid` |
| `claude --version` fails, times out after 5 seconds or prints something unparsable | `inactive` | `version_unknown` |
| Version below the minimum, compared numerically | `inactive` | `version_below_minimum` |
| Version at or above the minimum | `configured_unqualified` | `delivery_unverified` |

The field also carries `minimum_version`, `observed_version` when the version was read, and `model_route: "not_checked"`. It records neither `PATH` nor the executable's location. The status never fails verification by itself, because an unavailable adapter must not block the portable runner.

**What it covers:** one observation of the CLI's presence and version, and the validity of this repository's project configuration. The probe runs only `claude --version`, without inherited credentials.

**What it does not cover:**

- It is one field across the project hooks and the plugin hooks, and does not separate them.
- It reads the project file only, not effective settings across scopes.
- The developer client's model route is not checked, so `configured_unqualified` must not be read as compatible.
- It says nothing about whether events are delivered or whether rules load in a live session.
- Whether `claude --version` itself reaches the network is unknown.

Stored qualification values are separate from this status. Validation allows only these exact values, so a later claim needs recorded evidence and a deliberate change to the check.

| Field in `.claude/autobots.json` | Value | Describes |
|---|---|---|
| `assistant.event_delivery_qualification` | `not_tested` | The project hooks in `.claude/settings.json`. No qualification exercise is recorded |
| `upstream.delivery_plugin.event_delivery_qualification` | `not_qualified_one_pretooluse_event_observed` | The OhMyOrch plugin's hooks. One observed event qualifies nothing |

Neither value is a complete list of observations, and neither is `inactive`, which is only ever derived. The plugin doctor's `project-config` line means the plugin's project configuration was applied, which is neither field and qualifies nothing.

To arrange an unavailable adapter for one process, run these from the repository root. The first command should exit non-zero.

```sh
PATH=/usr/bin:/bin /bin/sh -c 'command -v claude'
PATH=/usr/bin:/bin /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter, .not_tested' .checks/harness/latest.json
```

Expected: the verifier exits 0, status `passed`, `inactive` with reason `unavailable`, and `not_tested` still lists Claude event delivery.

To arrange an incompatible adapter, use a stub that records its arguments:

```sh
STUB="$PWD/.checks/US-1.2/stub"
mkdir -p "$STUB"
cat > "$STUB/claude" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >> "$(dirname "$0")/args"
printf '2.1.200 (Claude Code)\n'
EOF
chmod +x "$STUB/claude"
: > "$STUB/args"
PATH="$STUB:/usr/bin:/bin" /opt/homebrew/bin/python3.12 scripts/verify.py --profile harness
jq '.status, .assistant_adapter' .checks/harness/latest.json
/bin/cat "$STUB/args"
```

Expected: the verifier exits 0, status `passed`, `inactive` with reason `version_below_minimum`, and the record holds only `--version`.

These results cover arranged conditions only, so they do not show how a real unavailable client behaves. Arranged runs overwrite the report, so finish with the normal `python3.12 scripts/verify.py --profile harness`.

## Forward ingestion on a disposable copy

This exercises `autobots-spec-ingest` and the read-only `autobots-spec-ingestor` against a synthetic source set. It never writes the real `SPECS.md`. `tests/harness/forward_arrangement.py` copies the retained fixture in `docs/engineering/evidence/HARNESS-ADAPT-001/forward-fixture/` to a new directory under `.checks` and applies fixed edits: two `SP-*` sections with coverage rows, a `Change:` line on one `IN PROGRESS` story, one story dependency, and a synthetic REQ-06. It refuses an existing destination and one outside `.checks`, so every run uses a new `F`. Nothing here is a claim about the real PRDs.

**Root substitution.** The skill's paths resolve from the repository root; here they resolve from the copy. The ingestor receives the absolute path of `$F/run-1` as its project root, and `scripts/specs.py` receives `--project-root "$R" --path SPECS.md`. The copy's document map has no `design` key, which is recorded as a gap and changes nothing.

**Actors.** The coordinator is the ingestor's paired caller: it arranges the copy, delegates the agent and persists the output verbatim. The tester runs `render` and `validate` and does all scoring. The skill's step 5 gives `render` and `validate` to the caller; this split is specific to this exercise, so that the coordinator performs no test. The delegation uses the developer assistant like every other specialist, and is not application inference.

**Expected result, fixed before the run.** US-1.1 stays `READY`. US-1.2 stays `IN PROGRESS` with its `Change:` line. US-1.3 stays `NEEDS CLARIFICATION` with its dependency. US-1.4 stays `BLOCKED`. One new story takes the next free ID, US-1.5, in EPIC-1. It cites `PRD.md#req-06-composer-autosave`, has `Dependencies: - US-1.2` and `Status: BLOCKED`, because REQ-06 states its trigger and US-1.2 is not `DONE`. Any other result, including `NEEDS CLARIFICATION` on the new story, is a finding, and nobody repairs the copy to match.

Shell variables do not carry between separate tool calls, so set them at the start of each call, and run from the repository root in bash or zsh, because process substitution is not available in `/bin/sh`.

**Coordinator**

1. Arrange the copy and keep an untouched comparison. This is skill step 1: then read `SPECS.md` and `CODEBASE.md` under `$F/run-1`.

   ```sh
   F=.checks/US-1.2/forward
   python3.12 tests/harness/forward_arrangement.py "$F/run-1"
   cp -R "$F/run-1" "$F/before"
   ```

2. Record the definitions on disk. Then, as skill step 2, delegate `autobots-spec-ingestor` with the absolute path of `$F/run-1`, the resolved paths, explicit decisions (none), existing identifiers, and a bounded scope: add stories for requirements with no story, and preserve the rest.

   ```sh
   F=.checks/US-1.2/forward
   shasum -a 256 .claude/agents/autobots-spec-ingestor.md .claude/skills/autobots-spec-ingest/SKILL.md > "$F/delegation.sha256"
   ```

3. Skill step 3: inspect the output and record what was seen. Make no edits; a discrepancy is a finding.
4. Skill step 4: persist the returned document verbatim to `$F/run-1/SPECS.md`. Keep `INGESTION SUMMARY` and the raw response outside the copy, as `$F/ingestion-summary.md` and `$F/raw-response.md`.
5. Skill step 5 passes to the tester. The coordinator runs no `render`, no `validate` and no scoring.

The hash covers only the file on disk. Unless the coordinating session started after the ingestor was last changed, the definition actually loaded is unproven, and the evidence says so.

**Tester**

```sh
F=.checks/US-1.2/forward
R="$F/run-1"
B="$F/before"
INGESTOR=.claude/agents/autobots-spec-ingestor.md
SKILL=.claude/skills/autobots-spec-ingest/SKILL.md
MANIFEST=docs/engineering/evidence/US-1.2/reviewed-manifest.json

python3.12 scripts/specs.py render --project-root "$R" --path SPECS.md
python3.12 scripts/specs.py validate --project-root "$R" --path SPECS.md
shasum -a 256 -c "$F/delegation.sha256"

test "$(jq -r --arg p "$INGESTOR" '.files[$p]' "$MANIFEST")" = "$(awk -v p="$INGESTOR" '$2 == p {print $1}' "$F/delegation.sha256")"

git diff --quiet HEAD -- "$SKILL"
test "$(git show "HEAD:$SKILL" | shasum -a 256 | awk '{print $1}')" = "$(awk -v p="$SKILL" '$2 == p {print $1}' "$F/delegation.sha256")"

diff <(grep -E '^(# EPIC-|### US-)' "$B/SPECS.md") <(grep -E '^(# EPIC-|### US-)' "$R/SPECS.md")
diff <(grep -E '^\| \[SP-' "$B/SPECS.md") <(grep -E '^\| \[SP-' "$R/SPECS.md")
diff <(grep -oE 'SP-[0-9]+' "$B/SPECS.md" | sort -u) <(grep -oE 'SP-[0-9]+' "$R/SPECS.md" | sort -u)

awk '/^### US-/{id=$2} /^Dependencies:/{d=1;next} /^Tasks:/{d=0} d&&NF{print id, $0}' "$B/SPECS.md" > "$F/deps-before.txt"
awk '/^### US-/{id=$2} /^Dependencies:/{d=1;next} /^Tasks:/{d=0} d&&NF{print id, $0}' "$R/SPECS.md" > "$F/deps-run.txt"
diff "$F/deps-before.txt" "$F/deps-run.txt"

awk '/^### US-/{id=$2} /^(Status|Change):/{print id, $0}' "$R/SPECS.md"
```

Expected:

- `render` and `validate` exit 0, and `shasum -c` exits 0.
- The `jq` comparison exits 0, so the hash at delegation equals the reviewed manifest's entry for the ingestor. It needs the manifest written at capture.
- `git diff --quiet` and the `git show` comparison exit 0, so the skill is unchanged from `HEAD` and its hash at delegation equals `HEAD`'s blob. The skill is expected unchanged, so the manifest does not list it.
- The first `diff` shows only added lines, for the new story.
- The two `SP` `diff` commands show no difference.
- The `deps` `diff` shows only `US-1.5: - US-1.2` added.
- The final `awk` shows the expected statuses above.

```sh
F=.checks/US-1.2/forward
R="$F/run-1"
B="$F/before"

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

Expected:

- The arranged copy validates, with counts 2 and 1 and the dependency line present. The rerun matches it.
- A second `render` changes nothing.
- On the stale copy, the first `validate` exits non-zero, then `render` and `validate` exit 0. This is the failure and recovery path.
- Both final `grep -c` commands print 0 and exit 1, which is not a failure here.
- The last `diff` shows no difference, so the other sources are untouched.

Then read the new story's `Source:` and Gherkin, and the copy's stories, against its `PRD.md`, `CONTRACT.md` and `CODEBASE.md`. Each scenario must trace to a cited source, and the seven-retry prototype must not become a requirement. Read `$F/ingestion-summary.md`: it must claim no delivery and say the agent ran no validation. One run shows one output, not that the ingestor is reliable.

The copies are disposable and ignored by Git. Use a new directory for each run instead of deleting one.

## Failure and recovery

| Symptom | Diagnosis and recovery |
|---|---|
| Stale navigation | Inspect the authored diff; render derived views; validate again |
| Missing source or malformed scenario | Locate the actual source; repair the reference/scenario or preserve the unresolved question; never invent success criteria |
| READY story with unfinished dependency | Keep the dependency and mark the story BLOCKED until its real prerequisite completes |
| Stale harness report | Run the relevant current checks; an old input hash cannot certify edited code |
| `verify.lock` exists | Read the recorded PID and establish whether its verifier is still running; only remove a confirmed stale lock, then rerun. Never delete another active check's lock |
| Completion hook blocks once | Run the portable checker or report the unavailable prerequisite. Repeated Stop processing does not loop forever or claim a missing check passed |
| Secret/destructive command denied | Use the separately authorized, target-guarded credential/maintenance procedure; this coding hook is not a general operations authorization mechanism |
| `assistant_adapter` reason `unavailable` | `claude` is not on this process's `PATH`. The portable runner still works; use it directly. Installing a client is a separate user decision, never part of a check |
| Reason `minimum_unknown` | `assistant.minimum_version_for_blocking_hook_failure` in `.claude/autobots.json` is absent or not three numeric parts. `project_configuration` reports the same fault. Restore the reviewed value from version history; do not guess one |
| Reason `configuration_invalid` | Run `jq '.checks[0].errors' .checks/harness/latest.json`. Any `project_configuration` error gives this reason, including one unrelated to the adapter, such as a lost rule link. Repair the named cause; do not widen the check |
| Reason `version_unknown` | `claude --version` failed, timed out or printed no three-part version. Run it directly to see which. Do not add credentials or environment to the probe |
| Reason `version_below_minimum` | The client is older than the recorded minimum. Updating it is a separate user decision; the portable runner still works meanwhile |
| Forward arrangement refuses its destination or reports a missing anchor | Choose a new `F` under `.checks`. A missing anchor means the retained fixture changed; report it instead of editing the fixture |
| Forward ingestion output fails `validate` or differs from the expected result | That is a finding. Report it and do not hand-repair the copy |

Parser and hook tests use temporary directories and clean up their own fixtures. The upstream clone, application data and unrelated services are not cleanup targets. Do not run reset/prune/down-with-volume-removal to repair this harness.

## Evidence and exercise status

A verified claim's last-exercised revision, date and result are recorded in the story's evidence, not in this runbook: see the [US-1.2 evidence summary](../evidence/US-1.2/summary.md), which also lists the steps exercised and those left unexercised. [HARNESS-ADAPT-001 evidence](../evidence/HARNESS-ADAPT-001/summary.md) is earlier evidence, for the initial harness adaptation, and is not current status.

Raw logs live under ignored `.checks`; reviewed redacted summaries remain versioned. An evidence manifest binds the tested source and configuration fingerprints. These commands imply no real Supabase or OpenRouter result, and live assistant event delivery stays unexercised.
