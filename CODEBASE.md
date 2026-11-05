# Autobots codebase context

**Inspected:** 2026-11-04. **Scope:** descriptive inventory; this file supplies no product requirements.

Analyzed revision: 34ae38f591dc2809d95819433bdceb2fb17b9e27

This describes that revision, which includes the OhMyOrch delivery setup in [HARNESS-OHMYORCH-001](docs/engineering/work-items/HARNESS-OHMYORCH-001.md).

## System Summary

A documentation and development-harness repository. It holds product PRDs, a source-traceable backlog and local tooling to plan, deliver and verify work. No product application exists yet.

## Repository Map

- `PRD-*.md`, `SPECS.md`: product and harness intent, and the execution backlog.
- `docs/engineering/`: technical contract, decisions, work items, runbooks and evidence. `prerequisite-inventory.md` there is the point-in-time inventory of repository assets and local tools.
- `docs/design/`, `docs/imagine/`: Luma tokens and generated interface concepts.
- `.claude/`: project skills, agents, rules, hooks and the document map in `autobots.json`.
- `scripts/`, `tests/harness/`: backlog tooling, harness verifier and their tests.
- `openspec/`, `SPEC-LOGS/`, `.claude/ohmyorch/`: OhMyOrch delivery state, per [Decision 0002](docs/engineering/decisions/0002-ohmyorch-delivery-loop.md).
- `research/`: research material. `research/upstream/` is ignored and not repository input.

## Runtime and Tooling

Observed on 2026-11-04, on this Mac. Presence is not qualification of an application environment.

- Python 3.12.16 at `/opt/homebrew/bin/python3.12`, used by project scripts and hooks.
- OpenSpec 1.13.2, jq 1.7.1, Bash 3.2.57 and Claude Code 2.1.314, used by OhMyOrch delivery.
- Node 26.13.0, uv 0.13.6, Supabase CLI 2.98.2 and Docker 29.9.2 are present. pnpm is absent.

## Evidence Paths

- `scripts/verify.py` writes its local report to `.checks/harness/latest.json` (ignored).
- Reviewed summaries are under `docs/engineering/evidence/<work-item-id>/`.
- Work records are under `docs/engineering/work-items/`.

## Unknowns

- Whether the OhMyOrch role identity and full story lifecycle hold in a live session; upstream 0.0.1 lists these as unproven.
- Whether installed tool versions satisfy the toolchain US-1.3 will lock.

## Current capabilities

The workspace contains the research PRDs, historical model evidence and an Option B technical contract. The technical contract preserves SP-001–SP-021 at `docs/engineering/option-b-contract.md`; root `SPECS.md` now contains a source-traceable backlog with 10 epics, 42 stories and generated navigation.

The current adaptation adds project-local `.claude` skills, specialist agents, scoped rules, command-hook configuration, a standalone backlog validator/navigation renderer, and a deterministic harness verifier. They are development tooling, not a product API or worker. Verification details belong to the adaptation evidence record; code existence is not proof a check passed.

The design artifacts include `PRD-Design-System.md`, the user-supplied light/dark token definitions at `docs/design/luma.css`, and generated interface concepts with a local gallery under `docs/imagine`. The design source is mapped into the harness and frontend guidance. These files document shadcn Luma with dark as the default; they do not implement an app theme provider or qualify browser behavior.

## Product implementation status

There is no implemented Next.js application, FastAPI service, LangGraph worker, application migration/seed set or project Supabase stack in this workspace. No local model runtime is part of the selected design. Public OpenRouter catalog research does not establish authenticated live model qualification.

No application lockfile/toolchain qualification or persistent database operation has been performed by this harness adaptation. The default `harness` profile is limited to the delivered development tooling. Future `fast`, `full`, `db` and `operations` profiles must report unavailable until implemented and tested.

## Integration points

- `.claude/autobots.json` maps source documents, backlog, technical contract and this inventory.
- `.claude/agents/autobots-spec-ingestor.md` reads sources and returns a proposed backlog; its caller writes approved changes.
- `scripts/specs.py` checks backlog structure, local source references, Gherkin, statuses and dependencies; it generates navigation from story bodies and promotes dependency-blocked stories whose dependencies are DONE. It cannot prove semantic source entailment.
- `scripts/story_manifest.py` hashes a story's changed files before review and compares them before archive.
- The upstream `ohmyorch` plugin provides `/ohmyorch:deliver`; `.claude/rules/ohmyorch-delivery.md` bridges it to the project contract.
- `scripts/verify.py` runs the delivered deterministic harness checks and records current input fingerprints/results locally.
- `.claude/hooks/dispatch.py` integrates selected events with bounded local checks. Script fixture tests and actual Claude event delivery have separate evidence.

## Upstream evidence and local constraints

OhMyOrch is cloned at `research/upstream/OhMyOrch`, pinned to `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. The spec-ingestion adaptation does not depend on running its plugin, shell/JQ tooling or OpenSpec lifecycle. Epic delivery does, per [Decision 0002](docs/engineering/decisions/0002-ohmyorch-delivery-loop.md): the plugin is installed from this checkout at local scope. The clone stays excluded from repository verification input and future commits.

Read-only local probes found Python 3.15.2, Python 3.12.16 at /opt/homebrew/bin/python3.12, and Claude Code 2.1.314 available. A separate process resolved plain python3 to macOS 3.9.6, so project hooks explicitly select the available 3.12 executable and scripts reject unsupported versions. The application Python baseline remains 3.12 as specified; the local interpreter probe is not a changed product requirement or a qualified application environment. No assistant model conversation was started to perform those probes.

## Gaps and evidence limits

H0/H1 and product work remain separately tracked in SPECS. Installed project files and synthetic hook tests do not establish an active, authenticated Claude/OpenRouter integration, a complete engineering baseline, or a working application. Update this inventory from actual observed changes and evidence; never derive new requirements from it.
