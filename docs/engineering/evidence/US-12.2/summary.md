# US-12.2: what a test could settle

**Class: real browser and real database, on a disposable stack, with a scripted worker or a fake transport.** No paid call and no persistent change. This doesn't establish H1 or product acceptance. US-12.3 repeats these checks on the final tree.

## Walking each surface in both themes

21 surfaces in dark and light, 42 in all, from `slice-visual.spec.ts`, which `scripts/qualify_identity.py` runs. Each surface's results are in [`walk.json`](walk.json), on `37d0c73` plus US-12.3's fixes, as that file says. [US-11.11's summary](../US-11.11/summary.md) lists the eight named surfaces that don't exist in the app.

| Checked on every capture | Result | Findings |
|---|---|---|
| Keyboard, tabbing from the top | 9 to 109 stops, none cut off. All 534 visible enabled controls in `main` were reached, counting a closed `details`'s summary and not what it hides, and focus never jumped back up the page | None. Nothing uses a positive `tabindex`. A radio group counts as reached when one of its radios is, as Tab lands on one and arrow keys move within it |
| Disabled controls, including `aria-disabled` | 12 across the captures, each named | None. Disabled controls are exempt from contrast under WCAG, and weren't measured |
| Zoom at 200% and 400%, as viewport widths 640 and 320 | No sideways scrolling of the page itself | None. Overflow inside an element isn't measured |
| Reduced motion | 3590 elements' computed transition and animation durations, none above 0.02 seconds when reduced | None. 0 elements have any motion by default, so nothing here had motion to reduce |

**Each check is shown failing.** A test in the same suite breaks a page on purpose: a link painted above the one before it, a control `inert` keeps Tab from, a positive `tabindex`, an element whose motion survives the reduced setting, and a disabled control with no name. Every one is reported.

**Two corrections on the way:** the first keyboard walk recorded 0 stops on most surfaces, because earlier steps had moved where Tab starts from, so it passed proving nothing. US-12.3's review then found the checks that replaced it couldn't fail either: document order is what Tab follows by definition, and a `:disabled` control can't take focus. These are their replacements.

## What stays a limit

| Row | What a test can't settle here |
|---|---|
| LC-03 | A real compaction. The browser's run compacts with a scripted model. Through the real SDK on a fake transport, the same goal and criteria are compared through the API, not a browser |
| LC-13 | A cut TCP connection. The browser's network was taken offline, which ends its stream |
| LC-15 | Real host downtime |
| LC-25 | Live dispatch. Background learning has no dispatch to inventory. The guard sees what Python opens, so a connection made inside a C library wouldn't show, as libpq's don't |
| LC-26 | Live request bodies |
| LC-34, DS-04, DS-05 | A person, and a screen reader. A page's zoom is a viewport width, not the browser's own control |
| MP-A06, MP-A07 | Live behavior of the routes, which is paid |
