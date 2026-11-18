# Decision 0021: Studio interface redesign

**Date:** 2026-11-07. **Authority:** the owner, who asked to "redesign the app totally" based on the [Studio concept set](../../imagine/README.md), one screen per sidebar section. This amends [PRD-Design-System.md](../../PRD/PRD-Design-System.md) DS-03 where noted and adopts the three proposals the concept set listed.

## Decision

| # | Choice |
|---|---|
| **R1. Scope** | Presentation only. Every screen takes the Studio look and layout; behavior, data, API calls, wording that states product facts, accessible names, roles and `data-*` hooks stay as they are. Nothing in the concepts that needs new data or behavior is built (see R6) |
| **R2. Tokens** | [luma.css](../../design/luma.css) stays the only palette and is not edited |
| **R3. Attention tone** | One paired extension in [studio-extensions.css](../../design/studio-extensions.css), beside the canonical file and imported after it by `apps/web/app/globals.css`, which keeps no color literal (`appearance.spec.ts`'s single-definition check), as DS-03 allows: `--attention` light `oklch(0.52 0.13 55)` (5.8:1 on `--background`, 5.3:1 on `--muted`), dark `oklch(0.828 0.189 84.429)` (11.5:1 on `--background`, 10.4:1 on `--card`), with `--attention-foreground` for filled use. It marks only what waits for a person: pending approvals, requested input, drafts. It always sits beside words |
| **R4. Status text colors** | No new color values. `globals.css` adds only aliases to existing tokens (`--success-text`, `--live-text`) and the `--serif` font stack. Success text is `--chart-4` in light (5.4:1) and `--chart-2` in dark (8.0:1); live text is `--primary` in light and `--sidebar-primary` in dark; failure is `--destructive`. Each state keeps its words or icon |
| **R5. Typography and navigation** | A system serif stack (no font download) for page titles and reading text. The sidebar keeps its nine links and their order within groups: the daily work (Home, Runs, Approvals), **Build** (Experts, Workflows) and **System** (Operations, Models, Tools, Settings). Tools stays directly before Settings, as Decision 0017 C9 and `tools.spec.ts` require, which is why it sits under System rather than Build as the concepts drew it |
| **R6. Not built** | Concept elements without a source of truth stay out: ⌘K search, an approvals count in the sidebar, a sidebar health line, a jobs chart, density and motion settings, a **System** theme (DS-02 offers only Dark and Light), approval keyboard shortcuts, "Generate from a run", a sidebar "New run" shortcut (Home holds the composer, and the first stop after the skip link stays Home, as `appearance.spec.ts` requires), and any count, price or date the API doesn't return. Each needs its own decision |

## What this gives up

- **Light tinted fills behind muted text.** Light `--muted-foreground` on `--muted` measures 4.34:1, so light surfaces stay on `--background` or `--card` with hairline borders; tints are dark-only.
- **Fidelity to the concepts** where R6 applies.

## What this doesn't establish

That the redesigned screens pass DS-04 beyond what `slice-visual.spec.ts` measures, or any H1 or product acceptance gate.

## Reversal

Revert the work item's commit. No data, contract or migration changes.

## Amended

[Decision 0022](0022-studio-product-surfaces.md) D1 brings R6's set-aside elements into scope as PRD-Studio.md specifies, and D2 replaces R5's grouping with Tools under **Build**. R1's presentation-only scope applies to this decision's own change only.
