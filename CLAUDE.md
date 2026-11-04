# Autobots

@AGENTS.md

Project-specific workflows live in `.claude/skills`; focused roles live in `.claude/agents`. Use `autobots-spec-ingest` to ingest or refresh the source-traceable backlog. Its read-only ingestor returns content for the coordinator to persist. Resolve documents through `.claude/autobots.json`.

The project hooks run local deterministic scripts. They do not configure an assistant model, install OhMyOrch as a plugin, start product services or authorize additional inference providers. Follow the documented runbook to inspect configuration and verify scripts; do not mistake a configuration file for proven live event delivery.
