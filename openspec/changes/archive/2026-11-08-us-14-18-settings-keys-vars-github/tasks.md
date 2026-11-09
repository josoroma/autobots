# Tasks

## 1. Storage (Owner-only versioned save and removal; The sealed secrets stay out of durable state)

- [x] 1.1 Migration 52: admit the provider `github` in `app_private.provider_credentials`. In `app_private.tool_key_settings`, admit `github_token`, `github_repository` and `browser_executor` and add a checked `value`. Record migration 52 as shipped for schema readiness

## 2. Resolution (Settings, then the environment, then .env, for all five; GitHub tools resolve per attempt)

- [x] 2.1 Generalize `application/tool_keys.py` to five items: sources, the members' values, a workspace view carrying the repository and switch, and per-attempt GitHub resolution
- [x] 2.2 Resolve the token and repository per attempt in the three GitHub adapters, their readbacks and the pull-request review

## 3. Approval binding (An approved GitHub write keeps its repository)

- [x] 3.1 Let a tool resolve its approval target with the call's context, and refuse an approved call `approval_target_changed` when the target now resolves differently or the recorded one is empty

## 4. Browsing switch (A saved disabled switch; A saved enabled switch)

- [x] 4.1 Resolve the switch per workspace for the catalog, admission and Expert save, and bind `browse_goal` per job only when the run's workspace has it enabled and the executor reports qualified

## 5. Settings (Settings → Keys & vars replaces Tool keys; Owner-only versioned save and removal)

- [x] 5.1 Replace the tool-key contract and routes with `/v1/settings/keys-and-vars`, with each item's check, and regenerate OpenAPI and the TypeScript client
- [x] 5.2 Rename the web page and nav to Keys & vars, add the two values, and update the repair text

## 6. Install (make start passes only the listed variables, as data)

- [x] 6.1 Pass `GITHUB_REPOSITORY` and `GITHUB_TOKEN` through `scripts/tool_keys_env.py`

## 7. Coverage and docs

- [x] 7.1 Unit tests, the disposable database check with the approval binding and the secret scan, the browser suite and the Makefile test
- [x] 7.2 Update the runbook, README, `.env.example` and CODEBASE
