# Imagine Autobots

Six visual concepts for the user experience of the selected **Option B**: an app running on this Mac, with OpenRouter for model inference.

**[Open the visual gallery](index.html)** · [Generation prompts](prompts.json) · [Artifact manifest](manifest.json)

These are generated interface concepts with sample data, not screenshots of an implemented product. Names, dates, prices, references, progress and validation statuses are illustrative.

## The experience

| Screen | What the user can understand and do |
| --- | --- |
| [01 · Start with a goal](01-home.png) | Describe the desired outcome, choose the model and run budget, and start work. Expert cards make specialist roles approachable. |
| [02 · Follow the work](02-run-workspace.png) | See the current plan, completed and pending steps, observable activity, an emerging artifact and estimated spend. Pause or cancel the run. |
| [03 · Review the exact change](03-approval.png) | Compare an existing protected local report with a proposed replacement. Approve that specific change or reject it. |
| [04 · Open the result and its evidence](04-result-evidence.png) | Read the completed brief, inspect attached sources and completion checks, download the artifact or start a similar new run. |
| [05 · Connect OpenRouter](05-model-settings.png) | Enter a missing key, save and validate it, and distinguish authentication from model availability and runtime qualification. |
| [06 · Make the task repeatable](06-workflow.png) | Arrange a reusable workflow, inspect a step, validate a draft and publish an exact version. |

The example journey is: configure a key when needed → describe a comparison task → follow the work → resolve an approval only if policy requires it → inspect the result → optionally reuse the process as a workflow. The gallery presents the main experience first and setup fifth; this is not a prescribed onboarding order.

## Visual direction

A quiet desktop workbench with a warm off-white canvas, white surfaces, charcoal text and forest-green primary actions. Amber draws attention to decisions and pending states. A persistent sidebar keeps goals, runs, experts, workflows, approvals, files and settings in the same place.

The artifact and the next useful action take priority over telemetry. Activity describes observable events; it is not a transcript of private model reasoning. Cost labels distinguish estimates from reported usage.

| Token | Proposed value |
| --- | --- |
| Canvas | `#F5F4F0` |
| Surface | `#FFFFFF` |
| Primary action | `#245B4A` |
| Text | Dark charcoal |
| Typography | System sans-serif, SF Pro / Inter-like |
| Corners | Approximately 10 px |
| Layout | Persistent sidebar, generous spacing, compact status rows |

These are proposed design values rather than measured raster colors or approved implementation tokens.

## Product alignment

- The app, its files and history live locally. Selected task context is sent to OpenRouter for inference; these screens do not imply offline AI.
- DeepSeek V4.1 Flash is the workspace default and GPT-6 Astra is an explicit choice. Friendly screen labels map to the exact profiles in the model-provider PRD.
- A missing key disables model features while local files, history, settings and drafts remain available. **Save & validate** does not start a task or establish runtime qualification.
- The approval screen illustrates replacement of a protected existing file. It does not establish approval for every ordinary artifact write or select an external connector.
- A completed run offers **Start similar run**, not resume. A workflow draft is separate from its published version and from a run.
- Completion checks describe structure and attached evidence; they do not certify that every generated statement is true.

Layout, sample controls and placeholder content are design proposals. The source specifications remain authoritative: [SPECS](../../SPECS.md), [Option B contract](../engineering/option-b-contract.md), [Next.js PRD](../../../PRD/PRD-NextJS.md), [LangGraph / Deep Agents PRD](../../../PRD/PRD-LangChain-Deep-Agents.md), [model providers](../../../PRD/PRD-Model-Providers.md) and [local deployment](../../../PRD/PRD-Local-Mac-Deployment.md).

## Generation and review

Generated with the built-in image-generation tool. The home concept supplied the shared visual reference for the remaining screens. Targeted revisions replaced invented vendor names with neutral examples, clarified local key storage versus authentication, distinguished an active step from completed progress, and highlighted changed comparison lines. The [prompt record](prompts.json) preserves the requested screen content and revisions.

All six final images were visually inspected for hierarchy, readable primary actions, consistent navigation, appropriate model choices and clear concept labeling. Raster text can contain small typographic irregularities; implementation needs real accessible components, keyboard behavior and responsive layouts.

See the [work record](../engineering/work-items/IMAGINE-001.md) and [verification evidence](../engineering/evidence/IMAGINE-001/summary.md) for scope and checks. No application acceptance criteria are marked complete by these images.

## Local viewing runbook

1. Open `docs/imagine/index.html` in a browser, or open any PNG directly.
2. Use the gallery navigation to jump between screens; click an image to view its full resolution.
3. Keep the gallery beside its six PNG files when sharing or moving it. It uses local assets, system fonts and no external scripts.
