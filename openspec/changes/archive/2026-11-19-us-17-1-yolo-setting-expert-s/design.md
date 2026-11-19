# Design

## Context

See proposal.md for why. What shapes the approach:
- **Approval is decided in one place.** `tool_gateway.hold_for_approval` asks the tool's `ApprovalPolicy` whether a call waits. `browse_goal`'s policy is `always=True`.
- **Workspace switches already exist.** The tool switches (migration 64, `application/tool_switches.py`, Decision 0033) are a per-workspace owner switch: an `app_private` table where no row means on, with an optimistic version, behind `MemberWorkspace` and `OwnerWorkspace` routes.
- **Expert versions are immutable `jsonb` configs** (`expert_versions.config`). A run records `expert_id` and `expert_version`, so a run's Expert config is fixed for its life.
- **Admission writes every run in one insert,** in `runs._insert_run_and_job`. A child stores what its parent froze.
- **Changing a tool's schema means a new tool version** (`tests/test_tool_schema_versions.py`), so `browse_goal`'s input and output stay as they are.
- **The BFF passes on any `/v1/settings/...` path** (`app/api/settings/[...path]`), and the web client is generated from OpenAPI.

## Goals / Non-Goals

**Goals:** the setting, its freezing and the YOLO test for a call; the approval waiver; the Expert's browse domains and the refusal before any container; and how they show in the Studio, PRDs and docs.

**Non-Goals:**
- browser-use, and any change to what a browse can do (US-17.3, US-17.4). A YOLO call still runs the read-only loop.
- A schema change to `browse_goal`.
- The composer's disclosure.

## Decisions

1. **The table, not Keys & vars.** The table is `app_private.browsing_settings (workspace_id pk, yolo boolean default true, version, notice_seen_at, updated_at)`. No row reads as on at version 0, so new and existing workspaces both start on (Y1) and nothing is backfilled. Keys & vars resolves from the environment first, and YOLO is a product setting the environment must not set. So it follows the tool switches' shape. Only the runtime role reads or writes it: no PostgREST, Realtime or browser role.

2. **Frozen in `runs.browsing_yolo`, default `false`.** The insert writes the first of these that exists:
   - the parent's frozen value;
   - else the workspace's row;
   - else `true`.

   Runs admitted before the migration read `false`, so they never skip approval.

3. **"The call is YOLO" is one read**, `browsing_settings.call_is_yolo(connection, scope)`: the run's frozen value AND the workspace's current value, read at the call. So turning it off applies at the next call, and turning it on can't reach a run frozen off (Y4).

4. **A waiver on the policy, not a special case in the gateway.** `ApprovalPolicy` gains `waived: Callable[[ToolContext], Awaitable[bool]] | None`. `hold_for_approval` checks it first and releases the call with no approval when it holds. A consequential external write never takes a waiver: the policy refuses to build one for that class.
   - The catalog's approval label gains `unless_yolo`, so the Tools page can say "every call, unless YOLO is on" (TC-02).
   - The approval reason text says the same, when a call does wait.

5. **The domain check sits at the top of `browse_goal`'s handler,** before `executor.sweep` or `start`. It runs only when the call is YOLO. The Expert's list is read from the run's own `expert_id` and `expert_version`. A domain is allowed when it is inside a listed one, a subdomain included (`contracts/browsing.within`). The codes are `browse_domains_missing` and `browse_domain_not_granted`.

6. **`typing: on` without a schema change.** `ToolDefinition` gains an optional `public_context(context) -> Mapping`. `begin_use` merges it into `input_public` when the row is written. `browse_goal`'s returns `{"typing": "on"}` for a YOLO call, and nothing otherwise.

7. **`browse_domains` on `ExpertConfig`.** It is a list of `DomainName`, at most 10, the same cap as a call's `allowed_domains`, defaulting to `[]`. Saving it is a config change, which already makes a new version (EX-02). The editor shows the field only while the draft grants `browse_goal`, directly or by its group.

8. **The routes.**
   - `GET /v1/settings/browsing`, for any member, returns `{schema_version, yolo, version, notice_pending, viewer_can_change}`. `notice_pending` is true only for the owner, until the notice is marked seen.
   - `PUT /v1/settings/browsing`, for the owner, takes `{yolo, expected_version}` and refuses `stale_version` or `owner_required`.
   - `POST /v1/settings/browsing/notice`, for the owner, marks the notice seen and is idempotent.

   Home reads the setting and, when `notice_pending`, shows the notice and marks it seen, so it shows once.

9. **Migration `20261119000065_browsing_yolo.sql`.** It opens with its traceability comment and Locks, Data and Recovery lines. The new table locks nothing. `alter table public.runs add column ... default false` is a catalog-only change in Postgres 15: a brief `ACCESS EXCLUSIVE` lock, and no rows are rewritten.

## Risks / Trade-offs

- **A YOLO call between US-17.1 and US-17.3** starts without approval but can still only read (Y15). It is less able than the read-only browse it replaces, never more.
- **`call_is_yolo` costs one extra read per `browse_goal` call,** which is negligible beside a browser session.
- **An Expert saved before this change has no `browse_domains`,** so under YOLO it can't browse until its owner lists domains. That is Y3's rule, and the refusal names the list so the owner knows what to do.
