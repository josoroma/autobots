# Tasks

## 1. US-20.4

- [x] 1.1 Add `scripts/browser_scoreboard.py`, which opens each address the owner names once for each browser, with no model, and records `opened`, `check`, `blocked` or `error`, the bytes and the seconds, keeping hosts only (Z15). Checked by a harness test under `tests/harness` with scripted openings.
- [x] 1.2 Show that no verification profile runs it. Checked by a harness test under `tests/harness`.
- [x] 1.3 Run it on `https://example.com/` and `https://example.org/` only, and record what was observed. Checked by its output and the egress proxy's log.
- [x] 1.4 Document it in the operations runbook, with the owner's reading of a site's terms before listing it on a stealth Expert, and that a site opening is not permission from that site (Z14). Update `README-DEV.md` and `CODEBASE.md`. Checked by reading them against Z14 and Z15.
