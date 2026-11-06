# US-11.11: final visual evidence

**Class: real browser, on a disposable stack with a scripted worker.** The pass line is WCAG 2.1 AA, by [Decision 0010](../../decisions/0010-contrast-pass-line.md). This doesn't establish H1, product acceptance or that the design is good, only what's measured here.

Captured by `slice-visual.spec.ts`, which `scripts/qualify_identity.py` runs. [`revision.json`](revision.json) holds the revision and a hash of the screens' source. [`results.json`](results.json) holds every measurement, and [`zoom.json`](zoom.json) the zoom results. Screenshots are in [`screenshots/`](screenshots/), named `<surface>-<theme>.png`. Their content is arranged test data.

Measured again on US-11.12's tree, after its review changed screens. `revision.json` records that base.

## Result

| Measured, across 42 captures of 21 surfaces in dark and light | Lowest | Line | Findings |
|---|---|---|---|
| Text, 2,032 elements | 4.74:1 | 4.5:1 | None |
| Input boundaries, 98 controls | 4.74:1 | 3:1 | None, after the correction below |
| Focus indicators, 559 stops, by keyboard and on each surface's own controls | 14.5:1 | 3:1 | None, after the correction below |
| A button under the pointer, 18 | 5.21:1 | 4.5:1 | None |
| Axe, WCAG 2.1 A and AA | | | 0 violations |
| Controls not from the shared components | | | 0 |

**Surfaces:** sign-in, key-setup, home, runs, run, inspector, experts, expert-editor, session, workflows, workflow-editor, workflow-monitor, approvals, approvals-empty, settings, models, operations, state-loading, state-error, state-empty and state-local-only.

## Found and corrected

| What | Measured first | Correction |
|---|---|---|
| An input's boundary | 1.26:1 in light, 1.57:1 in dark | `border-input` stays, and an inner edge in `--muted-foreground` is what identifies the control |
| The focus ring, in light | 2.48:1 to 2.58:1 | The `--ring` outline stays, and `--foreground` beside it is what reaches 3:1 |

Both are pairing corrections, as DS-04 asks first. **No token value changed, so no revision is proposed.** `--input` and light `--ring` remain below 3:1 by themselves, so anything that uses them alone would fail again. The shared components and `:focus-visible` are what prevent that.

Reading the screenshots also found Home's false "Inference is not configured yet", now corrected.

## Named in DS-03, and absent

| Surface | Why it isn't captured |
|---|---|
| Onboarding | No separate flow. Key setup is what a new owner meets, captured as `key-setup` |
| Dialogs and portals | The app has none |
| Menus | None apart from native selects, whose open lists the OS draws |
| Notifications | No toast surface. Results are inline status text |
| Charts | The app has none |
| Artifact previews | Artifacts download through a link. The list is on `run` |
| File lists | No screen lists a run's working files |
| Workflow canvas | The editor is a validated text form, so no edge or node marker exists |

## Use

| Check | Result |
|---|---|
| Keyboard | On Home: the skip link first, Enter on it, then Tab reaches the goal, and the next Tab reaches the model choice. Every surface's own controls had their focus measured |
| Zoom, at viewport widths 640 and 320, as 200% and 400% | No sideways scrolling on 8 screens. The shell's sidebar now stacks at narrow widths |
| Reduced motion | Nothing animates on 4 screens |
| Appearance | Changing it sends no `/api/` request, and runs, approvals and workflows read the same afterward |

## Limits

- **States measured:** default, hover and focus, plus the loading, error, empty and local-only states named above. A status message or refusal is only measured if it's on screen in a capture. Disabled controls are exempt under WCAG, and weren't measured.
- **Measured from computed styles,** by compositing backgrounds. Text over an image would be missed, and the app has none.
- **`state-local-only` is arranged** by refusing the page's API requests, and isn't the app with its API actually down. `boundary.spec.ts` covers that for Home.
- **Keyboard order was only walked on Home, as far as the model choice.** Other screens' focus was measured for up to 12 controls each, not their order.
- **Automated checks don't replace a person.** No screen reader was used.
- **Reduced motion and zoom were checked on the screens listed,** not all 21.
