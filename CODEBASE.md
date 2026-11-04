# Autobots codebase context

**Inspected:** 2026-11-04. **Scope:** descriptive inventory; this file supplies no product requirements.

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
- `scripts/specs.py` checks backlog structure, local source references, Gherkin, statuses and dependencies; it generates navigation from story bodies. It cannot prove semantic source entailment.
- `scripts/verify.py` runs the delivered deterministic harness checks and records current input fingerprints/results locally.
- `.claude/hooks/dispatch.py` integrates selected events with bounded local checks. Script fixture tests and actual Claude event delivery have separate evidence.

## Upstream evidence and local constraints

OhMyOrch is cloned at `research/upstream/OhMyOrch`, pinned to `fddfbf53c8c10d45782796cc9a7edf95bc8d3a07`. The project adaptation does not depend on running its plugin, shell/JQ tooling or OpenSpec lifecycle. The clone remains research material and is excluded from repository verification input and future commits.

Read-only local probes found Python 3.15.2, Python 3.12.16 at /opt/homebrew/bin/python3.12, and Claude Code 2.1.314 available. A separate process resolved plain python3 to macOS 3.9.6, so project hooks explicitly select the available 3.12 executable and scripts reject unsupported versions. The application Python baseline remains 3.12 as specified; the local interpreter probe is not a changed product requirement or a qualified application environment. No assistant model conversation was started to perform those probes.

## Gaps and evidence limits

H0/H1 and product work remain separately tracked in SPECS. Installed project files and synthetic hook tests do not establish an active, authenticated Claude/OpenRouter integration, a complete engineering baseline, or a working application. Update this inventory from actual observed changes and evidence; never derive new requirements from it.
