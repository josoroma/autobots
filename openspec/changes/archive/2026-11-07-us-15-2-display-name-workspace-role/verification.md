# Verification — us-15-2-display-name-workspace-role

Change: us-15-2-display-name-workspace-role
OpenSpec verify: VERIFIED — no blocking mismatch
Verified: 2026-11-07

## Findings

- **Completeness:** 10 of 10 tasks complete. 2 requirements added to `local-identity`.
- **"RLS bounds who reads and writes a name":** observed on a disposable stack in `python3.12 scripts/verify.py --profile db` (exit 0). The `app_db` cases passed:
  - a member reads its own name and a shared member's name, `Ada,Cy`;
  - another workspace reads no name, `0`;
  - a user updates their own name;
  - neither a shared member nor another workspace can change someone else's name, `0` rows each;
  - a forged insert for another user is refused by row-level security;
  - anonymous access is refused;
  - empty, 61-character and untrimmed names are refused by the check constraint.
  
  `supabase/migrations/20261107000042_user_profiles.sql` holds the table and policies.
- **"Edit my own display name", "Fall back to the email's local part", "Session summary and account footer" and "Account page":** observed in `identity_qualification`'s browser test "the account footer, the Account page and the display name" (passed, disposable stack). As member-c, who owns one workspace and is a member of another, it asserts:
  - the session's `display_name` is the email's local part and isn't saved;
  - two workspaces, with roles `member` and `owner` and non-empty names;
  - the footer shows the name, the role in the current workspace and "this Mac";
  - the menu offers Account and Sign out;
  - `/settings/account` shows an editable name, the read-only email, both roles and Sign out, and axe reports no violations;
  - saving "Cy Member" updates the footer;
  - an empty name and a 61-character name are refused with the 1-to-60 message;
  - the saved name survives both refusals and a reload.
  
  `services/agent/tests/test_api.py` also covers the fallback to "Member" without an email and `display_name_invalid` (422) for empty, blank and 61-character names, and passed in `full` and `fast`.
- **Found during implementation:**
  - The `full` profile's route inventory test needed `/v1/profile`.
  - The `db` profile found drift in the public row types, which was regenerated with `scripts/app_db.py types`.
  - The `db` profile also failed the upgrade case, because the disposable reset didn't drop the new table and function (task 1.3).
  
  After these fixes, `full` (exit 0), `db` (exit 0) and `fast` (exit 0) passed on the final inputs.
- **Design adherence:** not applicable, because `design.md` is optional and absent.
- **Note:** the API reads and writes names through the runtime role, scoped to the verified user in SQL. The authenticated-role RLS above bounds direct database access, which is the same boundary.
