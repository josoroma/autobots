# Imagine Autobots: quiet workbench

Six redesigned interface concepts for the selected **Option B** app, each in dark (the default) and light. The direction borrows the restraint of the best current AI products: a calm centered composer, a run that reads like a conversation beside its document, serif reading type for results, and one accent per screen.

**[Open the visual gallery](index.html)** · [HTML sources](source/) · [Artifact manifest](manifest.json) · [Earlier concepts](../README.md)

These are concept screens with fictional sample data (Tallyboard and Plainview are invented products), not screenshots of the implemented app.

## The screens

| Screen | Dark | Light | What changed from the previous set |
| --- | --- | --- | --- |
| 01 · Start with a goal | [01-home.png](01-home.png) | [light](01-home-light.png) | One centered composer with expert, limit and model inline; the OpenRouter disclosure sits right under it. Expert cards give way to suggestion chips. |
| 02 · Follow the work | [02-run-workspace.png](02-run-workspace.png) | [light](02-run-workspace-light.png) | Plan, sources and activity read as a thread; the draft document is the main canvas, not a footer row. Spend moves to a thin meter in the top bar. |
| 03 · Review the exact change | [03-approval.png](03-approval.png) | [light](03-approval-light.png) | A focused dialog over the paused run with a real unified diff, the run's reason and the scope of approval. |
| 04 · Result and evidence | [04-result-evidence.png](04-result-evidence.png) | [light](04-result-evidence-light.png) | The brief is set for reading; checks, numbered sources and reported usage move to a quiet rail. |
| 05 · Connect OpenRouter | [05-model-settings.png](05-model-settings.png) | [light](05-model-settings-light.png) | Settings with a sub-navigation. Keyless state, three separate statuses, Terra as default and DeepSeek not offered until qualified. |
| 06 · Make the task repeatable | [06-workflow.png](06-workflow.png) | [light](06-workflow-light.png) | A vertical flow on a dotted canvas with an inspector; draft versus published version is explicit. |

## Design principles

- **One loud thing per screen.** Luma blue (`--primary`, `--sidebar-primary`) marks only the next useful action, live state and links. Everything else is neutral.
- **Reading type for results.** A system serif (New York, Iowan Old Style, Charter, Georgia) for page titles and documents; the system sans for the interface; monospace for paths, diffs and model IDs.
- **Telemetry stays quiet.** Steps, activity and cost are always visible but never compete with the artifact.
- **Honest states.** Estimated cost while running and reported cost after; draft versus published; checks that verify structure, not truth.
- **Hairlines over boxes.** 1px `--border` separators and soft surfaces instead of nested cards; radius steps derive from `--radius`.

## Relation to the design contract

The screens consume [luma.css](../../../design/luma.css) unchanged. [quiet.css](source/quiet.css) only adds typography, radius steps derived from `--radius`, and semantic aliases: success is Luma's `--chart-3` (light) / `--chart-2` (dark), danger is `--destructive`, and attention is an added amber the palette doesn't define. Two choices go beyond what [PRD-Design-System.md](../../../../PRD-Design-System.md) states today, so they're proposals, not adopted requirements:

1. A serif display face for headings and documents.
2. The amber attention color for pending approvals and drafts.

Product semantics follow the current sources: Terra is the default for all 14 roles, DeepSeek isn't offered for new runs until qualified ([Decision 0013](../../../engineering/decisions/0013-release-closure.md)), saving a key never starts work, a completed run offers **Start similar run**, and approval covers one exact change.

## Rendering

Each PNG is a 1600×1000 viewport at 2× (3200×2000), rendered from the HTML in `source/` with the web app's pinned Playwright and a locally cached Chrome for Testing. Nothing is installed or downloaded.

```sh
node docs/imagine/archive/quiet-workbench-v1/source/render.mjs              # all screens, both themes
node docs/imagine/archive/quiet-workbench-v1/source/render.mjs 02-run-workspace
```

Set `CHROME_PATH` to use a specific browser. The sources also open directly in a browser: append `?theme=light` for the light theme.

## Local viewing runbook

1. Open `docs/imagine/index.html` in a browser. Use **Dark / Light** to switch every image.
2. Keep the gallery beside its PNGs, `source/quiet.css` and `../design/luma.css` when moving or sharing it. It uses system fonts and no external scripts.

## Earlier concepts

The previous Luma-dark raster set is in [archive/luma-dark-v1](../luma-dark-v1/), and the original warm-green exploration in [archive/warm-green-v1](../warm-green-v1/).
