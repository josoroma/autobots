# Design

## Context

See `proposal.md` for the observed state. Constraints: the implementer cannot write `.claude/*`, `AGENTS.md` or `CLAUDE.md`; `scripts/verify.py` must keep working with Claude absent (US-1.4 owns the wider runner); only the `harness` profile exists; and no check may call a model. The coordinator's decisions referred to below are listed in `implementation-plan.md`. They are the coordinator's, not user rulings, and stay open for the user to overturn.

## Goals / Non-Goals

**Goals:** make the rule-to-responsibility link mechanically enforced; hold skills and agents to DH-04's content; make "explicitly inactive" an observable result on arranged conditions; re-exercise ingestion against current definitions with checks that can fail.

**Non-Goals:** qualifying live event delivery; checking the developer client's model route; implementing pending profiles; hardening the dispatcher.

## Decisions

### D1. Granularity: rule files, `AGENTS.md` sections, and a DH-04 table

Coordinator decision: "each rule" means one link per `.claude/rules` file and one mapping row per rule-bearing `AGENTS.md` section. Skills and agents are covered by a per-file DH-04 table (D6) rather than per-rule links.

Each path-scoped rule gains one short final section with a Markdown link to `scripts/verify.py` naming its profile, and one to the `autobots-review-change` skill. DH-09 gives the profiles: contracts `fast`, database `db`, infrastructure `operations`, model gateway `full`, web and Python `fast` and `full`. Rules do not restate whether a profile is available, because that would be another copy to drift; the runner reports it. `delivery.md` already links DH-W01-06, the verification and review contract, so it stays unchanged. The bridge rule gains one line of links.

`AGENTS.md` gains one mapping section, likely titled `## Rule checks and review`, with these rows:

| Row | Check responsibility | Review responsibility |
|---|---|---|
| Opening paragraph | `scripts/specs.py` for source traceability | `autobots-review-change` |
| Work protocol | `scripts/specs.py`, `scripts/story_manifest.py`, DH-W01-06 | `autobots-reviewer` |
| Commands, including render scope and the profile statement | `scripts/verify.py`, whose pending profiles exit 2; `scripts/specs.py` | `autobots-verify-change` |
| Boundaries that matter | `scripts/verify.py` `project_configuration`, plus the pending profile that owns each layer | `autobots-review-change` |
| Completion evidence | `scripts/story_manifest.py`, DH-W04 to DH-W06 | `autobots-reviewer` |
| `.claude/settings.json`, which cannot carry links | `project_configuration` in `scripts/verify.py` | `autobots-review-change` |
| `CLAUDE.md` | Imports `AGENTS.md`. `project_configuration` in `scripts/verify.py` checks the hook configuration that its hook sentence describes, not the sentence itself, because `config_errors` never reads `CLAUDE.md` | `autobots-review-change` |

`CLAUDE.md`'s "documented runbook" becomes a real link, outside the managed block.

*Rejected:* one central mapping page, because a rule's link would then say nothing about that rule. Per-bullet links in every rule file, because each file's bullets share one layer and one responsibility.

### D2. The links are enforced by the existing configuration check

`config_errors` gains two checks, so `project_configuration` fails on either:

- A rule file with no Markdown link to an allowed target. Allowed targets are `scripts/verify.py`, `scripts/specs.py`, `scripts/story_manifest.py`, the verify and review skills, `autobots-reviewer`, and the anchor `PRD-Development-Harness.md#dh-091-work-item-evidence-contract`. A link to any other PRD anchor does not count. The negative fixture is a rule linking only to `PRD-Development-Harness.md#dh-07-supabase-migrations-seeds-and-database-quality`, so it cannot be confused with `delivery.md`, which passes through the DH-W anchor.
- An `AGENTS.md` without the mapping section, a `## ` heading in `AGENTS.md` with no row, a missing row for the opening paragraph, `.claude/settings.json` or `CLAUDE.md`, or a row without an allowed-target link. The mapping section's own heading is exempt, because D1 has no row for it and the real-tree test could otherwise never pass. Negative fixtures cover the missing section, a row with only a disallowed link, and a new heading with no row.

Link presence does not show the link is apt; review covers that.

### D3. Inactive is derived at validation, not stored

A helper in `scripts/harness_lib.py` returns a status, and `verify.py` records it as a top-level `assistant_adapter` report field and prints it in its summary. `report_state` requires three checks, so this is not a fourth check. The first matching row wins:

| Order | Observed | State | Reason |
|---|---|---|---|
| 1 | `claude` not found | `inactive` | `unavailable` |
| 2 | Minimum absent or unparsable | `inactive` | `minimum_unknown` |
| 3 | `config_errors` non-empty | `inactive` | `configuration_invalid` |
| 4 | `--version` fails, times out or is unparsable | `inactive` | `version_unknown` |
| 5 | Version below the minimum, compared numerically | `inactive` | `version_below_minimum` |
| 6 | Version at or above the minimum | `configured_unqualified` | `delivery_unverified` |

The two states are the whole set. Tests compare them by whole value, because `inactive` contains "active" and `configured_unqualified` contains "qualified", so a substring assertion would be wrong.

The field also carries `minimum_version`, `observed_version` when known, and `model_route: "not_checked"`. Coordinator decision: "incompatible" means presence, version and configuration validity. Route compatibility with the OpenRouter-only constraint (DH-01) is not checked, because checking would mean reading credentials or local settings, so `configured_unqualified` must not be read as compatible.

Any `project_configuration` error gives `configuration_invalid`, including one unrelated to the adapter, such as a lost rule link. That is deliberately conservative, and the check's `errors` list says which. While implementation is incomplete, the real tree reports this.

The helper runs only `claude --version`, with a default 5-second timeout that tests can shorten, and the same reduced environment as `run_check`: no inherited credentials. It starts the process in a new session and on timeout kills the process group, because a shell stub running `sleep` would otherwise hold the captured pipes open past the timeout and past `run_check`'s 60-second limit. It never records `PATH` or the resolved executable path. Status never fails verification by itself, because an unavailable adapter must not block the portable runner (DH-01, DH-02). `configured_unqualified` matches the runbook's existing "configured, event delivery unverified".

The field covers one observation: the CLI's presence and version, and the validity of the repository's project configuration. It does not separate the project hooks from the plugin hooks, and it does not establish effective settings across scopes, which DH-03 warns about. The runbook says so.

*Rejected:* storing `inactive` in `.claude/autobots.json`, which is false on this machine while hooks run. Treating `not_tested` as already meaning inactive, because nothing would validate anything and the Then clause would not be demonstrated.

### D4. Validation refuses activation claims

`config_errors` requires, by an allowlist of the two current literals, `assistant.event_delivery_qualification` to equal `not_tested` and `upstream.delivery_plugin.event_delivery_qualification` to equal `not_qualified_one_pretooluse_event_observed`. A prefix test would accept `not_tested_but_active`. It also requires `assistant.model_configuration` to equal `unchanged` and `assistant.minimum_version_for_blocking_hook_failure` to be a three-part numeric version string. Recording real qualification later needs evidence and a deliberate change to this check. Coordinator decision: the two literals stay unchanged, and the evidence explains that they are not a complete list of observations.

### D5. Repeat the forward exercise, and keep the retained fixture as its baseline

The retained fixture is reused as input and gets a regression test. The exercise itself is repeated, because the current skill's hash differs from the one in HARNESS-ADAPT-001's manifest and this story edits the ingestor.

The retained fixture cannot discriminate on two Then clauses: it has no `SP-*` requirement and no story depends on another. So `tests/harness/forward_arrangement.py` takes a destination argument, copies the fixture to that new directory under `.checks` and applies fixed synthetic edits, which the plan quotes: two `SP-*` sections with coverage rows, a `Change:` line on one `IN PROGRESS` story, one existing story dependency, and a synthetic REQ-06 that states its trigger, and whose expected story and status are fixed before the run. It refuses a destination that exists or lies outside `.checks`, and fails if an anchor it edits is missing. The regression test uses the same code, so the arrangement cannot drift from what is tested.

Coordinator decision on actors: the tester has no way to spawn an agent, and the scenario's actors are the ingestor and its paired caller. So the coordinator is the paired caller. It follows `autobots-spec-ingest`'s steps with the root substitution written in the runbook, delegates the read-only `autobots-spec-ingestor`, and persists the output verbatim to the disposable copy, recording the SHA-256 of the ingestor and skill at delegation. The skill's step 5 assigns `render` and `validate` to the caller; in this exercise the tester runs them, and does all scoring, so that the coordinator performs no test. The skill text is not changed, and the runbook states this difference.

The binding differs for the two files. The ingestor changes in this story, so its recorded hash is compared with its entry in the reviewed manifest. The skill is expected unchanged, so `current_files` in `scripts/story_manifest.py` leaves it out of the manifest. Its binding is instead `git diff --quiet HEAD` on the skill plus a comparison of its recorded hash with `HEAD`'s blob.

A session may hold the agent definition it loaded at start. Unless the coordinating session started after the ingestor was persisted, the evidence states that the definition actually loaded is unproven and that the hash covers only the file on disk.

The ingestor's change gets a test that fails on the current text, because `specs.py` already accepts `Change:` as prose, so a validator run proves nothing about the edit.

### D6. DH-04 content is inspected per file, before authoring

DH-04 requires each skill to define its trigger, relevant paths, prerequisites, workflow, expected evidence and failure behavior, and each agent to have scope, permitted tools, inputs and a result contract. Only the tool sets can be tested mechanically. The rest is inspection recorded as a per-file table, produced before protected content is authored so that any file needing a change is named in the plan first.

Closing a gap adds no behavior. Relevant paths come from the matching rule's `paths`: `autobots-contracts` from `contracts.md`, `autobots-docker-local` from `infrastructure.md`, `autobots-durable-worker` from `python-worker.md` and `autobots-model-gateway` from `model-gateway.md`. `autobots-implement-item` and `autobots-review-change` have no matching rule, so theirs come from DH-03's work-item, evidence and runbook paths: `docs/engineering/work-items/<id>.md`, `docs/engineering/evidence/<id>/` and `docs/engineering/runbooks/<id>.md`. Failure behavior restates existing contract text, such as `AGENTS.md`'s statement that skipped tests and missing tools never count as passing. A gap found in a protected path the plan does not name needs a plan amendment or a delivery block, as the bridge rule's first step requires.

### D7. The CLI syntax control runs early and must discriminate

DH-04 says to validate frontmatter against the qualified CLI, and the CLI's result on `.claude` has `manifest: null` and an empty `contents`. A failure on a lone broken skill might say nothing about frontmatter. `.claude` has no manifest, while upstream runs `claude plugin validate --strict --json plugins/ohmyorch` on a directory that has one, which may explain the empty result; whether it does is untried. So implementer pass 1 runs two paired controls under `.checks/US-1.2/validate-control/`, each a good and a broken copy that differ by one frontmatter fault in one skill:

- `.claude` shape, with `claude plugin validate --json`.
- Plugin shape, with `claude plugin validate --strict --json`: a scratch directory with a minimal `.claude-plugin/plugin.json` and copies of `skills/` and `agents/`. `--strict` treats warnings as errors, so the good copy may need manifest metadata; that is the only permitted adjustment, and a failure from a copied skill or agent is a finding.

A pair counts only if its good copy passes and its broken copy's error names the frontmatter fault. Rules stay on the harness check either way, and agents appear only in the good copies of the control, so a counted pair discriminates on that one skill fault and no further. Nothing in the sources defines what qualifies the CLI beyond its recorded version, so the evidence names the version used.

Coordinator decision, not a user ruling: if neither pair discriminates, the task closes on the harness frontmatter checks. No source provides this alternative. It does not meet DH-04's "qualified CLI" clause, so that clause is reported as not met, as an open limitation in the adaptation page, the evidence and the final report. The nearest basis is US-1.2#2's "record pinned provenance, syntax and optional adapter limitations" and H0.2's "Files validate against documented syntax". DH-09.1 says a required behavior that still depends on an unavailable check leaves the item incomplete or blocked, so if the user rejects this reading the story blocks. Either way the observed result goes into the adaptation page before capture, because a post-capture edit takes the reopen route.

The harness frontmatter test restricts keys to an allowlist: for skills `name`, `description`, `disable-model-invocation` and `allowed-tools`; for agents `name`, `description`, `tools`, `disallowedTools` and `model`; for rules only `paths`. Those are the keys DH-03 and DH-04 name plus the `model` key in use. Claude Code documents further keys, and using one means extending the test deliberately. Any agent `model` must be `inherit`.

## Risks / Trade-offs

See the Risks section of `implementation-plan.md`.
