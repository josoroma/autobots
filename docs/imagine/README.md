# Imagine Autobots

Six **shadcn Luma dark** visual concepts for the user experience of the selected **Option B**: an app running on this Mac, with OpenRouter for model inference.

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

The approved direction is **shadcn Luma, dark by default**, using the user's exact [light/dark tokens](../design/luma.css) and [design-system requirements](../../PRD-Design-System.md). Neutral near-black backgrounds, slightly raised dark cards, white text and blue primary actions replace the earlier warm-neutral/forest-green exploration. Green remains a chart/success/diff color rather than the primary-action brand.

A fresh visit is dark regardless of the OS setting. An explicit Light or Dark choice persists locally and is applied before paint in the planned app. The gallery presents six dark concepts; the CSS also defines the supported light theme. Generated raster colors approximate the palette, while the canonical CSS preserves exact OKLCH values, alpha and the 0.625rem radius.

The artifact and the next useful action take priority over telemetry. Activity describes observable events; it is not a transcript of private model reasoning. Cost labels distinguish estimates from reported usage. The persistent sidebar and core screen layouts remain consistent across the revised set.

The previous images and their provenance are retained as [superseded visual exploration](archive/README.md); they no longer define the app's appearance.

## Product alignment

- The app, its files and history live locally. Selected task context is sent to OpenRouter for inference; these screens do not imply offline AI.
- DeepSeek V4.1 Flash is the workspace default and GPT-6 Astra is an explicit choice. Friendly screen labels map to the exact profiles in the model-provider PRD.
- A missing key disables model features while local files, history, settings and drafts remain available. **Save & validate** does not start a task or establish runtime qualification.
- The approval screen illustrates replacement of a protected existing file. It does not establish approval for every ordinary artifact write or select an external connector.
- A completed run offers **Start similar run**, not resume. A workflow draft is separate from its published version and from a run.
- Completion checks describe structure and attached evidence; they do not certify that every generated statement is true.

Layout, sample controls and placeholder content are design proposals. The [design-system PRD](../../PRD-Design-System.md) owns the theme. The other source specifications remain authoritative: [SPECS](../../SPECS.md), [Option B contract](../engineering/option-b-contract.md), [Next.js PRD](../../PRD-NextJS.md), [LangGraph / Deep Agents PRD](../../PRD-LangChain-Deep-Agents.md), [model providers](../../PRD-Model-Providers.md) and [local deployment](../../PRD-Local-Mac-Deployment.md).

## Generation and review

Regenerated with the built-in image-generation tool, using the original layouts and the exact Luma dark tokens as references. The [prompt record](prompts.json) preserves the generation/edit instructions and theme source. These revisions preserve the reviewed progress, credential-disclosure and approval semantics.

All six final images were visually inspected for hierarchy, readable primary actions, consistent navigation, appropriate model choices and clear concept labeling. Raster text can contain small typographic irregularities; implementation needs real accessible components, keyboard behavior and responsive layouts.

See the [work record](../engineering/work-items/LUMA-001.md) and [verification evidence](../engineering/evidence/LUMA-001/summary.md) for scope and checks. No application acceptance criteria are marked complete by these images.

## Local viewing runbook

1. Open `docs/imagine/index.html` in a browser, or open any PNG directly.
2. Use the gallery navigation to jump between screens; click an image to view its full resolution.
3. Keep the gallery beside its six PNG files and preserve the relative `../design/luma.css` file when sharing or moving it. It uses local assets, system fonts and no external scripts.
