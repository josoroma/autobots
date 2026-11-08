# STUDIO-UI-001: Studio interface redesign

**Evidence:** [STUDIO-UI-001.json](STUDIO-UI-001.json). **Class:** static checks, local runtime and real browser on disposable stacks with a scripted worker. No model was called. This doesn't establish H1, product acceptance or that the design is good, only what's measured here.

The redesign is presentation only, by [Decision 0021](../../decisions/0021-studio-interface-redesign.md). Screenshots are in [`screenshots/`](screenshots/), named `<surface>-<theme>.png`, captured by `slice-visual.spec.ts` in the `db` profile. Their content is arranged test data.

## Profiles

| Profile | Result | What it covers here |
|---|---|---|
| `harness` | passed | Repository configuration, backlog, harness behavior |
| `full` | passed | Lint, format, typegen, typecheck, production build, Python suites, and the `appearance`, `boundary` and `tools` browser suites |
| `db` | passed | Every browser suite on disposable Supabase stacks, including `slice-visual` |

## Measured by `slice-visual`, 42 captures of 21 surfaces in dark and light

| Measure | Lowest | Line | Findings |
|---|---|---|---|
| Text, 3,310 elements | 4.54:1 | 4.5:1 | None |
| Input boundaries, 100 controls | 4.74:1 | 3:1 | None |
| Focus indicators, 553 stops | 17.18:1 | 3:1 | None |
| A button under the pointer, 18 | 6.28:1 | 4.5:1 | None |
| Axe, WCAG 2.1 A and AA | | | 0 violations |
| Keyboard order | | | 0 upward, 0 unreached |
| Zoom at 640 and 320 px | | | 0 sideways scroll |
| Reduced motion | | | Nothing moves |

The lowest text, 4.54:1, is light muted text on `--sidebar`: the group labels and the footer. It passes narrowly.

## Found during verification and corrected

| What | Found by | Correction |
|---|---|---|
| Color literals in `globals.css` | `appearance.spec.ts`, one token definition | The attention pair moved to [studio-extensions.css](../../../design/studio-extensions.css), imported after luma.css |
| A sidebar link before Home | `appearance.spec.ts`, keyboard flow | Removed; Home holds the composer |
| A 2.48:1 focus ring on every light surface | `slice-visual.spec.ts` | `shadow-xs` removed from focusable elements, so the `--foreground` ring applies again |
| Tools no longer directly before Settings | `tools.spec.ts`, read before the run | Tools moved under System, before Settings |

## Limits

- `/tools` isn't in `slice-visual`'s zoom paths. Its narrow layout was corrected after review, and not measured.
- The theme previews repeat luma.css values, and nothing checks they stay equal.
- `appearance`, `boundary` and `tools` ran in `full`; the slice suites only in `db`.
- Behavior equivalence where no spec asserts it rests on review, not on a test.
