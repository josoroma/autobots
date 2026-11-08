# Tasks

## 1. Data (RLS bounds who reads and writes a name)

- [x] 1.1 Add the `user_profiles` migration: a trimmed 1–60 character name, and RLS for own writes and shared-workspace reads, with runtime access
- [x] 1.3 Drop `user_profiles` and `shares_workspace_with` in the disposable reset, so the upgrade case can replay the newest migration, and regenerate the public row types
- [x] 1.2 Add RLS cases to `scripts/app_db.py` for own update, shared-workspace read, and an other-workspace user who can't read or write, plus an anonymous refusal and the length check

## 2. API (Edit my own display name; Fall back to the email's local part; Session summary and account footer)

- [x] 2.1 Add `SessionWorkspace`, the new `SessionSummary` fields, `ProfileView` and `ProfileUpdate` to the contracts
- [x] 2.2 Add `application/profiles.py` (workspaces with name and role, read and save the name) and the `/v1/profile` routes, with `display_name_invalid`
- [x] 2.3 Fill the session summary, falling back to the email's local part and then "Member"
- [x] 2.4 Regenerate the contract and the TypeScript client, and add Python API tests

## 3. Web (Session summary and account footer; Account page; Edit my own display name)

- [x] 3.1 Add the shell footer with name, role and "this Mac", and a menu with Account and Sign out
- [x] 3.2 Add `/settings/account` with the editable name, read-only email, role and Sign out
- [x] 3.3 Cover the web scenarios in `identity.spec.ts` with axe, and run the `db` profile
