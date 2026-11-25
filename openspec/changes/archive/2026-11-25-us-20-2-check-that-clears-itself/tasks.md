# Tasks

## 1. US-20.2

- [x] 1.1 Keep the challenge hosts as a fixed list in code, reachable as parts of a page by a session of browser-use on stealth only. Refuse a top-frame navigation to one and end the call `refused_action` (Z5, Z7). Checked by pytest under `services/agent/tests`, and by `scripts/qualify_browser_executor.py` with a challenge host arranged as example.org.
- [x] 1.2 On browser-use and stealth, tell a check that is the page (Google's "sorry" page, a Cloudflare challenge on the site's own host, a DataDome frame) from a Turnstile frame, which isn't a check, and from a reCAPTCHA, hCaptcha or Arkose one, which ends the call at first sight (Z8, Z9). `box` keeps its present rule (AB-04). Checked by pytest under `services/agent/tests` with fixture pages and a scripted model.
- [x] 1.3 Give a check that is the page 20 seconds to clear, holding the model's next request before admission. Then continue, or end the call `bot_check` (Z8). Checked by pytest under `services/agent/tests`, and by `scripts/qualify_browser_executor.py` with checks arranged on the qualification hosts.
- [x] 1.4 Tell browser-use on stealth never to press or answer a check, and record that this isn't enforced on a Turnstile widget (Z10). Checked by pytest under `services/agent/tests` and by reading the runbook.
- [x] 1.5 Add these to the stealth browser's required cases, and qualify again what the changed files bind. Checked by `scripts/qualify_browser_executor.py` on disposable stacks, reaching only the qualification hosts.
- [x] 1.6 Amend PRD-Tool-Catalog BX-03 and AB-04 as Decision 0038's "Requirements revised" lists. Update the operations runbook, `README-DEV.md` and `CODEBASE.md`. Checked by reading each against Z7 to Z10.
