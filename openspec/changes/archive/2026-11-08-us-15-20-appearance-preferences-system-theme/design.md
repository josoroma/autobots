## Decisions

- **System through next-themes:** `enableSystem` with `defaultTheme="dark"`. A first visit stays dark, and only the stored value `system` resolves through `prefers-color-scheme`, which next-themes also watches live. The before-paint script removes any other value, `System` included, so an invalid value can't become a class.
- **Preferences as root attributes:** set by the same before-paint script, so a reload paints them first. The control sets the same attributes. Choosing a default removes the stored key, so the browser keeps only deviations.
- **Documents:** the run's own prose (its goal, and evidence summaries in the inspector) uses `font-document`. Page and dialog titles stay serif, as Decision 0021 R5 sets them; they are interface, not documents.
- **Density:** Tailwind v4 derives every spacing utility from `--spacing`. Compact sets 0.2rem in place of 0.25rem, a 20% tightening everywhere, with no per-component rules.
- **Motion:** the forced rule matches the existing reduced-motion media query exactly, so forced and OS-driven reduction behave the same.
- **Out of scope:** SE-03's "stream text as it's written" isn't part of this story's acceptance.
