# US-2.5 visual and boundary evidence

DS-05 evidence, on top of revision `b67b921`, input fingerprint `59b46722e21e…`, 2026-11-05. Run with:

```sh
python3.12 scripts/qualify_web.py --retain docs/engineering/evidence/US-2.5/screenshots
```

Local processes in Chromium 156 through Playwright 1.64.1: the real API app with an arranged membership, and two real `next start` servers, one with its API unreachable. 32 browser tests passed, 0 failed, 0 skipped. These are runtime checks, and the concept images in `docs/imagine/` were not used as evidence.

## DS-05 checklist

| Item | Observed |
|---|---|
| Consumed tokens equal canonical | Every color token, including alpha, resolves identically to `docs/design/luma.css` in both modes, and `--radius` is 0.625rem. `globals.css` imports that file and defines no color. The built CSS keeps `oklch()` values |
| Fresh visit, both OS schemes | Dark in every animation frame sampled from before first paint, and no hydration error. The server's HTML is already dark with JavaScript off |
| Explicit light and dark | Light survives navigation and reload, with light in every sampled frame. Dark persists under a light OS |
| Invalid or unavailable storage | `system`, `garbage` and empty fall back to dark. With storage throwing, dark loads, a choice works for the session, and reload returns to dark |
| Named surfaces in both themes | Shell, sidebar, cards, status, form and dialog only. Later screens do not exist yet |
| Keyboard and focus | Skip link, navigation, a 2px solid focus outline, arrow keys on the theme radios, and a dialog that opens by keyboard, closes on Escape and returns focus |
| Contrast | axe-core WCAG 2.1 A and AA rules report no violation on both pages in both modes, including its color-contrast rule |
| Appearance has no side effect | Changing it issues no network request at all |
| Reproducible screenshots | [screenshots/](screenshots/) |

## Screenshots, reviewed by eye

`first-visit-dark-os-light.png`, `first-visit-dark-os-dark.png`, `settings-light.png`, `home-light-after-reload.png`, `dialog-dark.png`, `dialog-light.png`, `api-unavailable.png`. The first, `settings-light.png` and `dialog-dark.png` were opened and looked correct. The others were not individually reviewed.

## Limits

- **Synthetic identity.** Session tokens are signed by the qualification script, and membership is arranged. Real Auth is US-2.3.
- **Not checked:** browser zoom, reduced-motion behavior beyond the CSS rule, Safari and Firefox, charts and the workflow canvas, which don't exist yet. At a 640px width the theme control stays visible, and the sidebar stays fixed-width, with no mobile layout.
- **Automated contrast is partial.** axe can't judge every state, and hover and disabled states were not measured separately.
