# Runtime Q&A diagram sources

These static figures accompany [README-QA.md](../../../README-QA.md). Open the HTML sources directly in a browser; the SVG exports are embedded in the README. No server, JavaScript, external font, image or network request is required.

| Figure | Editable source | Markdown export | Reading |
|---|---|---|---|
| Model/tool cycle | [loop.html](loop.html) | [loop.svg](loop.svg) | Repeated decisions and observations; a final reply still requires recorded completion checks. |
| Delegation depth | [depth.html](depth.html) | [depth.svg](depth.svg) | Parent-child ancestry, not simultaneous execution. |
| Tool-call sequence | [tool-call.html](tool-call.html) | [tool-call.svg](tool-call.svg) | The model proposes; application code authorizes and executes. |

## Design provenance

Adapted from [Cathryn Lavery’s Diagram Design](https://github.com/cathrynlavery/diagram-design/tree/f24d98b05e2d7a5e68c2dedfe46e5b7173f50118), commit `f24d98b05e2d7a5e68c2dedfe46e5b7173f50118`, skill version 2.6, under the [MIT notice](LICENSE-diagram-design.txt). The minimal template, flowchart, tree, sequence, geometry, accessibility and export guidance informed these diagrams. The HTML is the editing source; SVGs are generated using the pinned skill’s `export_svg.py --system-fonts`.

The user selected Autobots’ existing design system. The HTML copies the exact light `:root` declarations from [Luma](../../design/luma.css), source SHA-256 `cfe0b1e970fd0b87a11d069dd6c22b71745030c5ac908a793767cdc4a2f0103f`. Diagram roles map paper→background, ink→foreground, secondary labels/connectors→muted-foreground, focal emphasis→primary, focal surface→primary-foreground, decorative rules→border. Focal-node subtitles use foreground on the pale primary-foreground surface; muted-foreground there measured below the 4.5:1 text threshold. The final minimum text contrast is 4.74:1. The app’s canonical tokens are unchanged. The light documentation figures do not change the application’s dark default.

The system sans and monospace stacks keep these files offline; Georgia supplies the editorial heading contrast. This is an explicitly disclosed typography adaptation, not a claim to bundle Diagram Design’s default Instrument Serif/Geist fonts. The project’s exact white Luma background takes precedence over the upstream warm-paper preference.

## Scope and verification

Each SVG uses a 960 × 600 `doc-inline` viewBox, accessible title/description, a local horizontal scroller in HTML and print scaling. Flowchart and tree nodes are bounded summaries; detailed reasons and limits remain in the Q&A. The sequence shows the permitted execution path, with denial/wait behavior described in its caption. The tree is one possible four-descendant history; its branches need not be open together.

Upstream self-check and geometry checks run against each HTML; local browser checks cover desktop rendering, standalone SVGs, mobile scrolling and absence of external requests. Results and screenshots are retained as documentation evidence under `.checks/DOC-QA-001/2026-11-05-doc-qa/`, summarized in [DOC-QA-001 evidence](../../engineering/evidence/DOC-QA-001/summary.md). They do not qualify product execution.
