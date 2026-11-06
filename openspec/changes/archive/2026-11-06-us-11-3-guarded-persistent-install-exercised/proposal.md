## Why

US-10.2's finding B1: every result so far comes from throwaway stacks, and no guarded path to a persistent database exists. Decision 0009 chose to build one, then stand up and exercise a real install on this Mac on its own ports, and authorized that stack, its data and configuration outside this repository, and goals under the shared US$1 cap.

## What Changes

- `scripts/persistent_install.py`: the install's recorded identity, loopback-only start, once-only setup, a guarded migration apply with no reset, and a capped goal.
- `scripts/qualify_persistent_apply.py`, in the `db` profile, tests each refusal on a disposable target.
- The real install, `autobots-install`, stood up and exercised: local Supabase, local app, operations, backup and upgrade runbooks, with stop and start, a backup restored into an isolated instance and one real migration.
- One real goal through the install's API and worker, with the inference switch off afterward.
- Runbooks corrected to what they do on a persistent stack. Two defects the real stack found are fixed: the backup's fact query couldn't be parsed without a disposable history table, and `cleanup` left a Supabase project's volumes behind.

## Capabilities

### New Capabilities

- `persistent-install`: how the one persistent install is identified, changed and exercised, and what's refused.

### Modified Capabilities

None.

## Impact

New scripts and `install.spec.ts`, `scripts/local_backup.py`, `scripts/disposable_db.py`, `scripts/supabase_stack.py`, `scripts/verify.py`, five runbooks and one migration on Terra's stored limits. **Outside this repository:** `~/.local/share/autobots-install`, and five named Docker volumes that stay until the owner removes them. Other projects' Docker stacks aren't touched.
