# Verification — us-15-5-approvals-inbox-count-badge

Change: us-15-5-approvals-inbox-count-badge
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

All browser results below come from `python3.12 scripts/verify.py --profile db` (exit 0) on a disposable stack, through `scripts/qualify_identity.py`.

- **Completeness:** 9 of 9 tasks complete. 1 requirement added to `approvals`.
- **"Waiting and Decided with counts":** the browser test "Waiting and Decided tabs with counts, J and K, and the badge" passed.
  - The tabs read `Waiting N` and `Decided M`, matching the API's `counts`.
  - The list shows every waiting request, with the first selected and its detail beside it.
  - J moves the selection to the second request, and K moves it back.
  - The Decided tab lists only approved, rejected, expired and withdrawn requests.
  - Pending, approved and rejected exist in the run. Expired and withdrawn weren't arranged, and the server's `DECIDED` set covers them.
- **"Facts of a request":** "a decided request shows its run, task, expiry and who decided" passed.
  - The approved request shows "For task: Send the team note", a recorded run goal, "Approved by you at …", and an expiry with both absolute and relative time.
  - Arranged: the run's plan task, and its tool use's task and operation ID, written as call completion writes them (`tests/db/approval_check.py`, case "the approved request is linked to a plan task", passed).
- **"The exact request, whole":** "the exact request whole, in Fields and JSON views" passed.
  - The digest shows the stored hash prefix and byte size.
  - The JSON view's `pre` equals the stored arguments.
  - Fields lists `to` and `body` in stored order. The body appears raw and is also rendered: `strong` "Totals", `code` "Q3", and two `li` items.
  - axe reported no violations.
  
  "a long request is shown whole, and one too long can't be approved" passed. A long request's tail appears in its `pre`, and the too-long request shows the alert. Its approval is refused by the server (`approval_too_large`, covered in `tests/db/blocker_check.py`) and by the shortcut handler.
- **"Shortcuts need a second press":** "a shortcut needs a second press, and never acts while typing" passed.
  - A single ⌘↵ announces "again within 2 seconds to approve". After 2.5 s it reads "Nothing was decided.", and the request is still pending.
  - Two ⌘⌫ presses while an arranged text field has focus do nothing.
  - Two ⌘⌫ presses otherwise reject it, and it appears under `status=rejected`.
- **"Sidebar badge from a count":** observed in the first test. The badge reads `N waiting`, where N comes from `/api/v1/approvals/count` and equals the Waiting count. The link's accessible name is "Approvals N waiting". `tools.spec.ts` ignores the badge when comparing link names.
- **Kept working:**
  - "an owner approves and rejects through the inbox", along with the other approval and US-13.1 tests, now selecting a request first.
  - `slice-workflows`' approval step.
  - `slice-visual` on every screen in both themes. A first run found focus moving up from the list into the detail. It's fixed by making the list a single tab stop on the selected request (task 2.4).
- **Found during verification, fixed before this record:**
  - The task link needed the operation ID on the tool use (task 2.5).
  - Switching tabs could show and click the previous tab's requests. The list now clears on a tab change while the tabs and counts stay (task 2.6).
  
  Then `db` (exit 0) and `fast` (exit 0) passed on the final inputs, after an earlier `full` (exit 0).
- **Design adherence:** not applicable, because `design.md` is optional and absent.
- **Limit:** markdown is rendered by a small reader built from React text nodes. It covers paragraphs, bullet lists, inline code and bold, and anything else shows as text.
