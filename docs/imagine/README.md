# Imagine Autobots: Studio

Nine redesigned screens, one for each section in the current app's sidebar (Home, Runs, Experts, Approvals, Operations, Workflows, Tools, Settings, Models). Each comes in dark (the default) and light. The aim is the finish of the best current AI products: a calm composer, tables you can read at a glance, side panels instead of extra page loads, and serif type for anything meant to be read.

**[Open the visual gallery](index.html)** · [HTML sources](source/) · [Artifact manifest](manifest.json) · [Earlier concepts](archive/README.md)

These are concept screens with sample data (Tallyboard, Plainview and `acme/tallyboard` are made up), not screenshots of the implemented app. When these screens were made, the running app at `http://127.0.0.1:3000/` was signed out, so each section showed only its empty or unavailable state. The content here comes from the web components, the domain model and the decisions instead.

## The screens

| # | Section | Dark | Light | The redesign |
| --- | --- | --- | --- | --- |
| 01 | Home | [01-home.png](01-home.png) | [light](01-home-light.png) | A centered composer with the Expert, budget and models inline, and attached `inputs/` files shown as chips. Under it: what leaves the Mac, which models and tools the run would use, what needs you, and recent runs. |
| 02 | Runs | [02-runs.png](02-runs.png) | [light](02-runs-light.png) | A table with filter tabs (All, Active, Needs you, Finished), canonical states in words and color, and estimated versus reported spend. A side panel shows the selected run's plan, spend meter and controls. |
| 03 | Experts | [03-experts.png](03-experts.png) | [light](03-experts-light.png) | Cards that show each Expert's role, model and granted tools. Select several and a floating dock starts a coordinator session. An Expert that can change something outside says so on its card. |
| 04 | Approvals | [04-approvals.png](04-approvals.png) | [light](04-approvals-light.png) | An inbox beside the full request: requester, run, task, expiry, the exact fields and digest, and what approving releases. Keyboard shortcuts for deciding. |
| 05 | Operations | [05-operations.png](05-operations.png) | [light](05-operations-light.png) | A one-line verdict, then eight checks in the panel's own wording, a 24-hour jobs chart, model route qualification and retention. |
| 06 | Workflows | [06-workflows.png](06-workflows.png) | [light](06-workflows-light.png) | Published and draft versions shown explicitly in the list. A side panel previews the published flow on a dotted canvas, including its approval gate, plus recent executions. |
| 07 | Tools | [07-tools.png](07-tools.png) | [light](07-tools-light.png) | The catalog grouped by what each tool does, with network, cost, approval and availability on every row. A detail panel shows limits, which Experts and workflows it's granted to, and its input schema. |
| 08 | Settings | [08-settings.png](08-settings.png) | [light](08-settings-light.png) | Appearance gets visual theme cards, reading type with a live sample, density and motion. Models and Operations are linked from here, not nested inside it. |
| 09 | Models | [09-models.png](09-models.png) | [light](09-models-light.png) | The OpenRouter connection with separate statuses, the three approved profiles with capabilities, prices and qualification, and per-role overrides with `researcher` on Sol. |

## What changes across every screen

- **Grouped sidebar.** The same nine sections, grouped into work (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings). The sidebar adds New run (⌘N), search (⌘K), a waiting-approvals badge and a one-line health status.
- **List plus panel.** Runs, Workflows, Tools and Approvals keep the list on screen and open detail in a side panel, so you can scan the list without losing your place.
- **The product's own words.** States, check messages and tool facts reuse the app's existing wording, such as "Waiting for approval", "The disk has room." and "Every call waits for a person".
- **One loud thing per screen.** Luma blue marks only the next action, a selection and live state. Amber means something waits for you. Green and red are used only for outcomes.
- **Reading type.** A system serif for page titles and documents, the system sans for the interface, and monospace for tool IDs, model IDs and paths.

## Relation to the design contract

The screens use [luma.css](../design/luma.css) unchanged. [quiet.css](source/quiet.css), carried over from the previous set, adds typography, radius steps derived from `--radius`, and semantic aliases. [studio.css](source/studio.css) adds only layout components on top: tables, segmented controls, side panels and callouts. Three choices go beyond what [PRD-Design-System.md](../PRD/PRD-Design-System.md) says today, so they're proposals, not adopted requirements:

1. A serif display face for headings and documents.
2. An amber attention color for pending approvals, input and drafts.
3. Grouped sidebar navigation with search and a health line.

Product details follow the current sources: three approved profiles, with Terra the workspace default, Sol the researcher's built-in default and DeepSeek not offered until qualified ([Decision 0019](../engineering/decisions/0019-sol-profile-and-browser-use.md)); the tool groups, the 20-call metered limit and tool providers ([Decision 0017](../engineering/decisions/0017-tool-catalog.md)); the 14 model roles; and approval covering one exact request. Counts, prices, dates and run histories are sample values.

## Rendering

Each PNG is a 1600×1000 viewport at 2× (3200×2000), rendered from the HTML in `source/` with the web app's pinned Playwright and a locally cached Chrome for Testing. Nothing is installed or downloaded.

```sh
node docs/imagine/source/render.mjs              # all screens, both themes
node docs/imagine/source/render.mjs 07-tools
```

Set `CHROME_PATH` to use a specific browser. The sources also open directly in a browser: append `?theme=light` for the light theme.

## Earlier concepts

The previous six-screen "quiet workbench" set, which was organized by user journey rather than by section, is in [archive/quiet-workbench-v1](archive/quiet-workbench-v1/). Older sets are listed in the [archive README](archive/README.md).
