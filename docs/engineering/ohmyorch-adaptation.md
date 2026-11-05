# OhMyOrch provenance and adaptation

This page covers the spec-ingestor adaptation from Decision 0001. Epic delivery now uses the real plugin; [Decision 0002](decisions/0002-ohmyorch-delivery-loop.md) supersedes the plugin, OpenSpec and continuation exclusions below and lists how the two systems are bridged.

Source: [josoroma/OhMyOrch spec-ingestor](https://github.com/josoroma/OhMyOrch/blob/fddfbf53c8c10d45782796cc9a7edf95bc8d3a07/plugins/ohmyorch/agents/spec-ingestor.md). The requested repository was shallow-cloned to `research/upstream/OhMyOrch` and pinned to commit `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. The checkout is ignored by Git. The ingestion adaptation does not execute its code; since Decision 0002 the delivery plugin runs from it.

## Preserved behavior

- Read product sources before decomposition; CODEBASE is descriptive evidence only.
- Return source-traceable epics/stories with Given/When/Then acceptance.
- Keep IDs stable and distinguish READY, NEEDS CLARIFICATION, BLOCKED, IN PROGRESS and DONE.
- Preserve source conflicts and unanswered decisions rather than inventing product behavior.
- Derive the table of contents, status table and dependency diagrams from story bodies.
- Let the coordinator persist the ingestor's proposed content and own delivery status.

## Adapted for Autobots

| Upstream design | Project adaptation |
|---|---|
| Plugin document map and `${CLAUDE_PLUGIN_ROOT}` | `.claude/autobots.json` maps the actual project documents; no plugin-root dependency |
| Read-only ingestor includes Bash | Project ingestor has Read/Grep/Glob only; caller runs validation and writes output |
| Plugin `doctor`, shell/JQ implementation | Standalone Python backlog tools and repository verification, independent of Claude |
| Plugin OpenSpec/archive/continuation workflow | Existing DH-W plan/implementation/review/verification/runbook evidence contract |
| Existing prose specification | SP-001–021 retained in the mapped engineering contract; EPIC/US backlog adds actionable decomposition |
| Legacy partial/unverified acceptance caveat | Required checks remain unpassed until actual evidence exists; static/mock results never qualify live behavior |
| Plugin distribution/update behavior | Project-local reviewed skills, agents, rules and command-hook settings; no plugin install/update action |

No upstream application model choice, additional paid service, global Claude setting or automatic continuation loop was imported. The clone itself is not an application dependency. Repository metadata at the inspected revision did not include a root license file; this project retains provenance and authors project-specific instructions/scripts rather than redistributing the upstream plugin package.

## Qualification boundary

The local parser checks syntax, source locations, identity, dependency/status consistency and generated navigation. Independent source review is still needed: a valid link does not prove acceptance is supported by the source. Hook script fixtures do not prove actual assistant event delivery. The qualified local runbook and evidence record distinguish these claims explicitly.

## Validation record (US-1.2)

**Pinned provenance.** Commit `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. `plugins/ohmyorch/agents/spec-ingestor.md` at that commit has SHA-256 `091932c9408125f9b54e9748bc7f443ff11cd3033ad2ded0f7baa1a60bbcaa5d`. The sentence in [`upstream.json`](evidence/HARNESS-ADAPT-001/upstream.json) saying no upstream plugin was installed or executed is historical: it was true of that evidence, and [Decision 0002](decisions/0002-ohmyorch-delivery-loop.md) has since installed the plugin for delivery. The ingestor adaptation still does not depend on it.

**Syntax checks that exist.**

| Check | Covers |
|---|---|
| `project_configuration` in [`scripts/verify.py`](../../scripts/verify.py) | Hook configuration shape, skill and agent `name` and `description`, rule links, the `AGENTS.md` mapping, and the qualification fields |
| [`tests/harness/test_assistant_assets.py`](../../tests/harness/test_assistant_assets.py) | Allowlisted frontmatter keys for skills, agents and rules, agent `model` being `inherit`, names matching locations, instruction links including fragments, and representative rule paths |
| [`scripts/specs.py`](../../scripts/specs.py) | Backlog grammar, sources, Gherkin and generated navigation |
| `claude plugin validate` | Skill frontmatter, on the conditions below |

**CLI control, observed 2026-11-04 with Claude Code 2.1.314.** Each pair is a good and a broken scratch copy under `.checks/US-1.2/validate-control/`, differing by one fault: the `description` line removed from `skills/autobots-python/SKILL.md`. A pair counts only if its good copy passes and its broken copy's error names that fault. Each pair ran on copies taken before the rule, skill and agent edits, and again under `final/` on copies taken after them, with the same results.

| Pair | Command | Good copy | Broken copy | Counts |
|---|---|---|---|---|
| `.claude` shape: copies of `skills/`, `agents/`, `rules/` and `settings.json` | `claude plugin validate --json` | Exit 0, `success: true`, empty `contents` | Exit 0, `success: true`, a warning on path `description` | No. Exit status does not discriminate, and there is no error |
| Plugin shape: copies of `skills/` and `agents/` with a scratch manifest | `claude plugin validate --strict --json` | Exit 0, `success: true`, empty `contents` | Exit 1, `success: false`, a warning on path `description` for that skill | Yes, on the reading below |

The plugin-shaped pair counts on one reading: the fault appears in the `warnings` array with `errors` empty, and `--strict`, documented as treating warnings as errors, turns it into the failure. The scratch manifest needed `version`, `description` and `author` added to `name`; with `name` alone, both copies failed, the good copy only on those three manifest warnings. No skill or agent was changed for this. If that reading is rejected, neither pair counts, and DH-04's "validate frontmatter against the qualified CLI" clause is not met.

**What these results do not show.**

- `contents` lists only files with findings, so an empty list passes nothing by itself. The discrimination shown is one skill fault. Agents appear only in the good copies, and rules stay on the harness check.
- No source defines what qualifies the CLI beyond a recorded version, so this names the version used and claims no qualification.
- The runs used scratch copies, not the repository's `.claude` directory.
- Valid syntax does not show that rules, skills or agents load in a live session, or that hook events are delivered.

**Adapter limits.** `assistant_adapter` in the harness report is derived at validation and is either `inactive` or `configured_unqualified`. It is one field across the project hooks and the plugin hooks, reads the project file rather than effective settings across scopes, and does not check the developer client's model route, so `configured_unqualified` must not be read as compatible. Inactive results on this machine come from arranged conditions: Claude Code is present here, so no real adapter has been inactive. The stored qualification values stay unchanged and are not a complete list of observations. The [runbook](runbooks/development-harness.md#read-the-adapter-status) explains how to read all of these.

Exercise results for the later steps, including the forward ingestion, are in the [US-1.2 evidence summary](evidence/US-1.2/summary.md).
