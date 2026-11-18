# Autobots

@AGENTS.md

Project-specific workflows live in `.claude/skills`; focused roles live in `.claude/agents`. Use `autobots-spec-ingest` to ingest or refresh the source-traceable backlog. Its read-only ingestor returns content for the coordinator to persist. Resolve documents through `.claude/autobots.json`.

The project hooks run local deterministic scripts. They do not configure an assistant model, install OhMyOrch as a plugin, start product services or authorize additional inference providers. Follow the [documented runbook](docs/engineering/runbooks/development-harness.md) to inspect configuration and verify scripts; do not mistake a configuration file for proven live event delivery.

<!-- OHMYORCH:BEGIN project -->
## OhMyOrch project workflow

Use the installed plugin's /ohmyorch:doctor and /ohmyorch:deliver commands.
Project intent: docs/PRD/PRD-LangChain-Deep-Agents.md. Backlog: SPECS.md.
Current-state evidence: CODEBASE.md (generate it only through analysis).
Each READY story is one OpenSpec change: propose, apply, verify, archive.
The next action is derived from project artifacts, never from chat memory.
Generic rules are bundled in the plugin; updates never copy executable code here.

<!-- OHMYORCH:END project -->
