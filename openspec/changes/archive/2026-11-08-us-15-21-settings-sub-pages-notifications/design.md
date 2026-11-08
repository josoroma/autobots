## Decisions

- **Notification source:** the app has no workspace-wide event stream, so the notifier polls the run list's "Needs you" group through the app's own API. It polls only while the setting is on and permission is granted. The first poll after start, or after a setting change, sets a baseline, so only a run that newly waits is told. Each run and status is told once.
- **The retention summary carries the viewer's role**, so one request settles both the workspace and whether to offer Operations. Retention stays changeable only through the owner-only Operations route.
- **Shortcuts:** one list in `lib/shortcuts.ts` drives the Keyboard page. Today the app's shortcuts are the Approvals keys and the skip link's first Tab. ⇧⌘O (D16) arrives with the search palette story and is added there.
- **Layout:** the section navigation comes before the page, so keyboard order runs nav then content. The links to Models and Operations sit in a separate list, because they lead out of these sections.
