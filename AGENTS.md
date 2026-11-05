# Autobots engineering contract

Build the selected Option B: native local Next.js + Python FastAPI/LangGraph/Deep Agents, local Supabase in Docker, and OpenRouter-only inference. Read the mapped documents in `.claude/autobots.json`; begin with `SPECS.md` and the sources for the selected story. `CODEBASE.md` describes current implementation, never product intent.

## Work protocol

- Preserve source requirements and stable `SP-*`, `EPIC-*` and `US-*` identifiers. Keep unsupported behavior as a question, conflicts as blocked work, and dependencies explicit. Do not infer new requirements from code.
- Choose one bounded authorized work item. Record its plan, actual implementation, independent review, verification and exercised runbook/evidence according to PRD-Development-Harness.md DH-W01–06. Small changes use short records. Review is not another user-permission ceremony. Exception, by the user's [Decision 0003](docs/engineering/decisions/0003-openspec-only-delivery.md): routine delivery through `/ohmyorch:deliver` follows the OpenSpec lifecycle in `.claude/rules/ohmyorch-delivery.md`, whose archived change is the record, with no independent review unless the user or a story's acceptance asks for one.
- Writer agents own disjoint files. Reviewers inspect without repairing implementation. The coordinator validates handoffs and owns status changes. Neither ingestion nor a successful syntax check marks a story DONE.
- Honor the user's current scope. Adapting this development harness does not authorize implementing the product, starting databases or performing paid model qualification.
- Shared H0/H1 comes before feature work. The harness profile proves repository checks only, and `fast` and `full` add local static checks, focused tests and a build; `db` adds synthetic fixtures on a disposable target; the unimplemented `operations` profile must fail explicitly. Never report all H1 or product acceptance gates passed from synthetic fixtures.

## Commands

Run from the repository root using the local Python interpreter (scripts support Python 3.12+):

```sh
python3.12 scripts/specs.py validate
python3.12 scripts/specs.py render
python3.12 scripts/verify.py --profile harness
```

`render` changes only generated backlog navigation, not story intent/status/tasks. Use it after an authorized backlog edit, then validate. The harness verification runs local deterministic tests without model calls or package installs. `fast` adds the Python and web checks for what changed, and `full` runs all of them plus the production build, using prepared environments without installing. Exit codes: 0 passed, 1 a check failed, 2 a prerequisite is unavailable or a check could not run. `db` creates a marked disposable Docker target for synthetic migrations, seeds and authorization, then removes only that target. `operations` is defined but unavailable until its tooling is implemented; no other profile substitutes for it.

## Boundaries that matter

- All application model calls use the two approved OpenRouter profiles and the shared gateway. No fallback, local model server, implicit evaluator, hosted tracing or alternative provider. Keep runtime clients/keys out of durable state. Do not change developer-client model credentials as part of harness setup.
- Pydantic/OpenAPI owns public API contracts; generated TypeScript clients consume them. SQL owns persistent schema. LangGraph state/reducers and UI view models remain distinct. Use canonical states from the preserved Option B contract; terminal runs cannot resume.
- Workers require leases/fencing, receipts, budgets and cancellation before live inference. Checkpoint ownership needs actual enforcement, not only a pre-dispatch check.
- Migrations and repeatable seeds are separate. No persistent reset, volume removal or cloud project linking in ordinary checks. Use target-guarded disposable integration environments. Never seed real secrets or pending inference jobs.
- Keep secrets, `.env`, provider master keys and persistent volumes outside model/tool workspaces and evidence. No environment dumps. Hooks provide limited guardrails, not OS confinement or protection against arbitrary shell code.
- Do not install dependencies, start services, mutate databases or call a model automatically in a hook. Actual assistant event delivery must be qualified separately from feeding synthetic JSON to a hook script.

## Completion evidence

Preserve reviewed redacted manifests/summaries under `docs/engineering/evidence/<work-item-id>/`, from `docs/engineering/templates/` and validated by `scripts/evidence.py`; bulky raw results belong in ignored `.checks`. Bind results to source/config/lock/verifier fingerprints. Record expected and observed assertions, commands, exit codes, review findings and limitations. Mocked, static, disposable and live evidence are different. Templates, skipped tests and missing tools never count as passing implementation evidence.

## Rule checks and review

Each row names the check and the review responsibility for one source of rules. A link shows who owns the rule, not that a check passes. A pending profile names a future check, so review is what applies to that layer until the profile exists.

| Rule source | Check responsibility | Review responsibility |
|---|---|---|
| Opening paragraph | [`scripts/specs.py`](scripts/specs.py) for source traceability | [`autobots-review-change`](.claude/skills/autobots-review-change/SKILL.md) |
| Work protocol | [`scripts/specs.py`](scripts/specs.py) and [DH-W01–06](PRD-Development-Harness.md#dh-091-work-item-evidence-contract) | [`autobots-reviewer`](.claude/agents/autobots-reviewer.md) |
| Commands | [`scripts/verify.py`](scripts/verify.py), whose pending profiles exit 2, and [`scripts/specs.py`](scripts/specs.py) for render scope | [`autobots-verify-change`](.claude/skills/autobots-verify-change/SKILL.md) |
| Boundaries that matter | `project_configuration` in [`scripts/verify.py`](scripts/verify.py), plus the pending profile that owns each layer | [`autobots-review-change`](.claude/skills/autobots-review-change/SKILL.md) |
| Completion evidence | [`scripts/verify.py`](scripts/verify.py) and [DH-W04–06](PRD-Development-Harness.md#dh-091-work-item-evidence-contract) | [`autobots-reviewer`](.claude/agents/autobots-reviewer.md) |
| `.claude/settings.json` | `project_configuration` in [`scripts/verify.py`](scripts/verify.py), because this file cannot carry links | [`autobots-review-change`](.claude/skills/autobots-review-change/SKILL.md) |
| `CLAUDE.md` | It imports `AGENTS.md`. `project_configuration` in [`scripts/verify.py`](scripts/verify.py) checks the hook configuration that its hook sentence describes, not the sentence itself, because that check never reads `CLAUDE.md` | [`autobots-review-change`](.claude/skills/autobots-review-change/SKILL.md) |
