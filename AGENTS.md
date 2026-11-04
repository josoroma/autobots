# Autobots engineering contract

Build the selected Option B: native local Next.js + Python FastAPI/LangGraph/Deep Agents, local Supabase in Docker, and OpenRouter-only inference. Read the mapped documents in `.claude/autobots.json`; begin with `SPECS.md` and the sources for the selected story. `CODEBASE.md` describes current implementation, never product intent.

## Work protocol

- Preserve source requirements and stable `SP-*`, `EPIC-*` and `US-*` identifiers. Keep unsupported behavior as a question, conflicts as blocked work, and dependencies explicit. Do not infer new requirements from code.
- Choose one bounded authorized work item. Record its plan, actual implementation, independent review, verification and exercised runbook/evidence according to PRD-Development-Harness.md DH-W01–06. Small changes use short records. Review is not another user-permission ceremony.
- Writer agents own disjoint files. Reviewers inspect without repairing implementation. The coordinator validates handoffs and owns status changes. Neither ingestion nor a successful syntax check marks a story DONE.
- Honor the user's current scope. Adapting this development harness does not authorize implementing the product, starting databases or performing paid model qualification.
- Shared H0/H1 comes before feature work. The installed harness profile proves repository checks only; unimplemented app/database/operations profiles must fail explicitly. Never report all H1 or product acceptance gates passed from synthetic fixtures.

## Commands

Run from the repository root using the local Python interpreter (scripts support Python 3.12+):

```sh
python3.12 scripts/specs.py validate
python3.12 scripts/specs.py render
python3.12 scripts/verify.py --profile harness
```

`render` changes only generated backlog navigation, not story intent/status/tasks. Use it after an authorized backlog edit, then validate. The harness verification runs local deterministic tests without model calls or package installs. Profiles `fast`, `full`, `db` and `operations` are defined but unavailable until their corresponding tooling is implemented; they are not aliases for a passing harness check.

## Boundaries that matter

- All application model calls use the two approved OpenRouter profiles and the shared gateway. No fallback, local model server, implicit evaluator, hosted tracing or alternative provider. Keep runtime clients/keys out of durable state. Do not change developer-client model credentials as part of harness setup.
- Pydantic/OpenAPI owns public API contracts; generated TypeScript clients consume them. SQL owns persistent schema. LangGraph state/reducers and UI view models remain distinct. Use canonical states from the preserved Option B contract; terminal runs cannot resume.
- Workers require leases/fencing, receipts, budgets and cancellation before live inference. Checkpoint ownership needs actual enforcement, not only a pre-dispatch check.
- Migrations and repeatable seeds are separate. No persistent reset, volume removal or cloud project linking in ordinary checks. Use target-guarded disposable integration environments. Never seed real secrets or pending inference jobs.
- Keep secrets, `.env`, provider master keys and persistent volumes outside model/tool workspaces and evidence. No environment dumps. Hooks provide limited guardrails, not OS confinement or protection against arbitrary shell code.
- Do not install dependencies, start services, mutate databases or call a model automatically in a hook. Actual assistant event delivery must be qualified separately from feeding synthetic JSON to a hook script.

## Completion evidence

Preserve reviewed redacted manifests/summaries under `docs/engineering/evidence/<work-item-id>/`; bulky raw results belong in ignored `.checks`. Bind results to source/config/lock/verifier fingerprints. Record expected and observed assertions, commands, exit codes, review findings and limitations. Mocked, static, disposable and live evidence are different. Templates, skipped tests and missing tools never count as passing implementation evidence.
