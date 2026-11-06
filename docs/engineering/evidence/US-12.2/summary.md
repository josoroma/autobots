# US-12.2: what a test could settle

**Class: real browser and real database, on a disposable stack, with a scripted worker or a fake transport.** No paid call and no persistent change. This doesn't establish H1 or product acceptance. US-12.3 repeats these checks on the final tree.

## Walking each surface in both themes

21 surfaces in dark and light, 42 in all, from `slice-visual.spec.ts`, which `scripts/qualify_identity.py` runs. Each surface's results are in [`walk.json`](walk.json), on `eff3498` plus this story's change. [US-11.11's summary](../US-11.11/summary.md) lists the eight named surfaces that don't exist in the app.

| Checked on every capture | Result | Findings |
|---|---|---|
| Keyboard order, tabbing from the top, up to 60 stops | 9 to 60 stops, each later in the document than the one before | None. Nothing uses a positive `tabindex` |
| Disabled controls | 12 across the captures, none focusable and each named | None |
| Zoom at 200% and 400%, as viewport widths 640 and 320 | No sideways scrolling | None |
| Reduced motion | Nothing animates for longer than a millisecond | None |

**One correction on the way:** the first keyboard walk recorded 0 stops on most surfaces, because earlier steps had moved where Tab starts from, so it passed proving nothing. It now runs first, and 0 stops counts as a finding.

## What stays a limit

| Row | What a test can't settle here |
|---|---|
| LC-03 | A real compaction. The browser's run compacts with a scripted model. Through the real SDK on a fake transport, the same goal and criteria are compared through the API, not a browser |
| LC-13 | A cut TCP connection. The browser's network was taken offline, which ends its stream |
| LC-15 | Real host downtime |
| LC-25 | Live dispatch. Background learning has no dispatch to inventory |
| LC-26 | Live request bodies |
| LC-34, DS-04, DS-05 | A person, and a screen reader. A page's zoom is a viewport width, not the browser's own control |
| MP-A06, MP-A07 | Live behavior of the routes, which is paid |
