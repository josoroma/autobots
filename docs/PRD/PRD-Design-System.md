# PRD — Autobots design system: shadcn Luma

**Decision date:** 2026-11-04.  
**Status:** approved design requirement from the user's supplied CSS; application implementation and visual/accessibility qualification remain pending.  
**Applies to:** the selected Option B Next.js UI, including any shared UI retained for the TypeScript alternative. Python, Docker and Supabase do not own presentation tokens.  
**Canonical tokens:** [docs/design/luma.css](../design/luma.css). Both selector blocks reproduce the user's supplied declarations without changing values.

“Luma” names this project's user-supplied palette. Do not replace it with a similarly named preset, infer a shadcn CLI preset identifier, or substitute generated default colors. The earlier warm-neutral/forest-green concepts are superseded as visual guidance. Their historical artwork remains in [the archive](../imagine/archive/warm-green-v1/).

## DS-01 — Preserve the exact theme tokens

Use shadcn/ui components with semantic CSS variables. The canonical file contains the complete light `:root` block and dark `.dark` overrides. Preserve every OKLCH component, alpha, token name and `--radius: 0.625rem`. The dark theme inherits the base radius.

The palette is neutral near-black with blue primary actions in dark mode. Green chart tokens are a chart palette, not a replacement brand or primary-action color.

| Purpose | Light | Dark |
| --- | --- | --- |
| App background | `oklch(1 0 0)` | `oklch(0.145 0 0)` |
| Main text | `oklch(0.145 0 0)` | `oklch(0.985 0 0)` |
| Card/popover surface | `oklch(1 0 0)` | `oklch(0.205 0 0)` |
| Primary action | `oklch(0.488 0.243 264.376)` | `oklch(0.424 0.199 265.638)` |
| Sidebar primary | `oklch(0.546 0.245 262.881)` | `oklch(0.623 0.214 259.815)` |
| Border | `oklch(0.922 0 0)` | `oklch(1 0 0 / 10%)` |
| Input | `oklch(0.922 0 0)` | `oklch(1 0 0 / 15%)` |

This table is a reading aid; the CSS file is authoritative for all declarations, including foreground pairs, secondary/muted/accent, destructive, rings, five chart colors and every sidebar token. Keep a single maintained token definition when the app is implemented. Import or deterministically consume this source through the frontend global stylesheet; avoid separately edited copies.

shadcn's documented theming model uses semantic surface/foreground pairs, CSS variables and a dark-class override. Configure `tailwind.cssVariables: true` and expose the tokens through the installed Tailwind version's supported semantic mapping. [shadcn theming](https://ui.shadcn.com/docs/theming)

## DS-02 — Dark is the default

A first visit, missing preference, invalid preference or unavailable preference storage renders dark. The Mac/browser operating-system preference does not change that default. An explicit user selection of **System**, **Dark** or **Light** persists locally and is restored on subsequent visits; **System** follows the operating-system preference only once the user has chosen it. *Amended by [Decision 0022](../engineering/decisions/0022-studio-product-surfaces.md) D2, which added System; before it, an old `system` value resolved to dark and the selector offered only Dark and Light.*

Use a dedicated nonsecret appearance preference such as `autobots.theme`. This permission to store an appearance choice does not permit storing credentials, provider responses or sensitive run state in browser persistence.

The Next.js implementation uses the shadcn `next-themes` integration pattern, adapted to this explicit product decision:

```tsx
<ThemeProvider
  attribute="class"
  defaultTheme="dark"
  enableSystem={false}
  themes={["dark", "light"]}
  storageKey="autobots.theme"
  disableTransitionOnChange
>
  {children}
</ThemeProvider>
```

The official example defaults to the system; this app deliberately sets dark and disables system mode. Confirm these options against the package version actually locked during implementation. This snippet is a requirement illustration, not an installed dependency or working provider. [shadcn Next.js dark mode](https://ui.shadcn.com/docs/dark-mode/next)

The server shell has a dark fallback and the theme bootstrap resolves a valid saved preference before visible content paints. Configure any necessary script nonce/CSP through the actual app security setup. Limit hydration suppression to the theme-mutated root attributes; render theme-dependent controls safely after mount rather than suppressing unrelated warnings. Verify both no-light-flash on a fresh dark visit and no-dark-flash when restoring an explicit light choice. If browser storage is unavailable, toggling may apply for the session and reload falls back to dark without crashing.

Keep the appearance control available in the shared shell or Settings → Appearance, including while no OpenRouter key exists. Switching appearance changes presentation only: it cannot launch inference, start/stop a run, validate a key or alter persisted agent execution state.

## DS-03 — Apply semantic tokens across the whole UI

Use the same design system for sign-in, onboarding, home/goal entry, run/plan/activity views, experts, workflow editor, approvals/diffs, artifact previews, file lists, model settings, dialogs, menus, notifications, empty/loading/error states and offline/local-only views.

| Component/surface | Required treatment |
| --- | --- |
| Page shell | `background` and `foreground` |
| Panels, cards and artifact chrome | `card` and `card-foreground` |
| Menus, selects and dialogs | `popover` and `popover-foreground` |
| Primary buttons | `primary` and `primary-foreground` |
| Secondary/hover/selected surfaces | Semantic secondary, muted and accent pairs |
| Inputs and focus | `input`, `border`, `ring`; visible keyboard focus |
| Sidebar | Dedicated sidebar surface/text/accent/primary/border/ring tokens |
| Charts | `chart-1` through `chart-5`, with labels/patterns as needed |
| Workflow canvas and inspector | App/card/muted tokens; readable typed edges and selected-node indicators |
| Destructive actions/errors | `destructive` plus an explicit label/icon and measured readable text |

Expose every color to Tailwind semantic utilities, including charts and sidebar colors. Map the radius scale to the canonical base rather than hardcoding component-specific values. Use real accessible shadcn components, not images as the interface. Keep layout spacing and typography consistent; the palette does not require changing the selected architecture or feature scope.

Never infer a run state from a color alone. Success, approval, active-step, removed-line and added-line treatments require text or icons. Additional semantic status tokens may be introduced only as documented paired light/dark extensions with measured contrast; they must not overwrite or silently reinterpret the supplied palette. Decorative gradients, green brand CTAs, beige backgrounds and hardcoded white-only panels from the old concepts are not the active direction.

## DS-04 — Preserve usability and state meaning

Check keyboard navigation, focus visibility, labels, disabled controls, text contrast, non-text contrast, zoom and reduced-motion behavior in both themes. Use selected/active markers and text in addition to color for workflow edges, plans, charts and diff lines. Do not treat the existence of a supplied palette or a generated image as an accessibility pass.

Where a combination fails, first correct semantic pairing, focus thickness/offset, labeling, or component structure. If a token value must change, record a proposed revision against this design contract rather than silently substituting another palette.

Theme work preserves these existing requirements:

- Activity shows explicit plans and observable actions, not private model reasoning.
- OpenRouter is the only inference route. Local storage does not imply offline inference.
- The key is stored locally and sent to OpenRouter for authentication; task context is separately disclosed.
- A missing key leaves local non-AI navigation and appearance usable.
- Approval describes an exact action; changing themes cannot decide it.
- Estimated versus reported costs, active versus completed steps, draft versus published workflows and terminal versus resumable runs remain distinct.

## DS-05 — Verification and design evidence

At implementation time, record checks against the actual locked app, not just this documentation:

1. Compare the consumed `:root` and `.dark` declarations to the canonical CSS, including alpha values and inherited radius.
2. Exercise fresh storage with both OS schemes, explicit light/dark persistence and reload, invalid/unavailable storage, first paint and hydration.
3. Inspect the named surfaces, dialogs/portals, chart and workflow rendering in both themes; test keyboard/focus and responsive layouts.
4. Measure contrast in the actual rendered component states. Retain findings, fixes and remaining limits.
5. Confirm appearance changes issue no model/task requests and do not mutate run, approval or workflow state.
6. Capture reproducible screenshots and retain reviewed runbook evidence under the work item's evidence directory.

The current [concept gallery](../imagine/index.html) illustrates the dark default. Generated raster artwork approximates the palette and layout; exact CSS values and product behavior are established by source and future implementation checks. The light theme is specified by the exact CSS even though the six regenerated concepts depict dark mode.

## Implementation handoff

Apply this contract through SP-014 and the local frontend foundation story in [SPECS.md](../../SPECS.md), before feature screens establish competing styles. Follow the [development harness](PRD-Development-Harness.md) delivery loop. No story is complete solely because the tokens, requirements or concept images exist.
