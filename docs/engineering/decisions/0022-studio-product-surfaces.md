# Decision 0022: Studio product surfaces

**Date:** 2026-11-07. **Authority:** the owner. They asked for the app to "look and work like" the nine [Studio concepts](../../imagine/README.md), and for the tools the concepts' Experts and workflows need. They read [the Studio features plan](../../plan/studio-features.md) and answered its open questions in this session, then answered the backlog's six open questions with D14 to D17. Their answers are recorded in [the plan's owner answers](../../plan/studio-features.md#owner-answers).

This decision approves [PRD-Studio.md](../../../PRD-Studio.md) and schedules EPIC-15. It amends [Decision 0021](0021-studio-interface-redesign.md) R5 and R6, [PRD-Design-System.md](../../../PRD-Design-System.md) DS-02, [Decision 0017](0017-tool-catalog.md) C9 and [Decision 0007](0007-first-connector-github-issues.md), as listed below.

## Decision

| # | Choice |
|---|---|
| **D1. Scope** | The elements Decision 0021 R6 set aside are now in scope. Each is specified in PRD-Studio.md. "Presentation only" no longer bounds the Studio work; every other requirement still does. Each element is built only where real data backs it. Nothing shows sample data |
| **D2. Conflicts: the concepts win** | **DS-02** offers **System**, **Dark** and **Light**. Dark stays the default for a first visit, a missing value and an invalid value. **System** follows the OS preference, and only when the person chose it. **Decision 0017 C9:** Tools moves under **Build**, after Workflows, and `tools.spec.ts` changes with it. **Decision 0021 R5:** the sidebar becomes the work group (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings) |
| **D3. Keyboard** | ⌘K opens search. ⌘N opens a new run. Both live in the shell after the skip link, and the skip link stays the first stop. In the approvals inbox, ⌘↵ approves the focused request and ⌘⌫ rejects it, and each needs a confirming second press within 2 s. Neither shortcut acts while focus is in a text field. J and K move between requests |
| **D4. Streaming result text** | The run's *result* text may stream as ephemeral, coalesced `result.text.delta` events. PRD §11.3 already allows "token deltas may be ephemeral/coalesced". They never carry private reasoning, tool arguments or raw framework values (SP-011). Durable events and the stored artifact stay authoritative. A **Stream text as it's written** preference turns live display off in the browser |
| **D5. Narrow metrics** | Operations may show counts and measured values the server already computes: worker count, applied migrations, storage and disk bytes (never paths), catalog fetch time, a loopback check, jobs per hour for 24 hours, and the database answer time as the p95 of the last 20 readiness probes. This narrows Decision 0013's deferral of metrics to exactly these. Nothing leaves the Mac, and there is no tracing |
| **D6. GitHub** | Decision 0007's single operation widens to **one configured repository**, `GITHUB_REPOSITORY`, with: four read-only tools (`github_list_pull_requests`, `github_list_workflow_runs`, `github_search_issues`, `github_read_file`); the existing `create_github_issue`, which gains an optional `labels` input; and a second consequential connector, `github_open_pull_request`, which needs approval on every call. The token stays in the worker environment, fine-grained to that repository: Issues read/write, Pull requests read/write, Contents read/write, Actions read, Metadata read. No tool takes a repository from the model |
| **D7. Pull-request idempotency** | The branch is `autobots/<operation_id>`, and the PR body carries the operation ID as a marker. A retry first reads back that branch and any open PR from it, and returns the existing PR if one is found. Commits touch only the paths the approved request names. The approved request shows the full diff, the base branch and the title. Merging is never a tool |
| **D8. Workflow drafts** | Each workflow may hold one saved draft beside its published versions. Publishing from a draft checks the expected version and creates the next immutable version. Runs and routines bind only published versions, as PRD §7.3 requires |
| **D9. "Needs you"** | `waiting_approval` and `waiting_input`. A `paused` run counts as Active |
| **D10. Display name** | An editable per-user profile name, with workspace-member RLS. It falls back to the part of the sign-in email before `@`. It's shown only to members of a shared workspace and to the user |
| **D11. Budgets** | Home's budget chip and the per-execution budget of a workflow allow **US$0.25 to US$5.00**, in steps of US$0.25. The default is US$1.00. A choice is never above the workspace's remaining daily cap (MP-07). The chosen limit is frozen on the run |
| **D12. Repository** | `josoroma/bot-test`, for qualification and use. Every test uses a fake transport (Decision 0017 C5). A live call needs the owner's token in the environment and a separate, capped authorization |
| **D14. Small definitions** | **Read only** means an Expert with no consequential tool; internal writes such as `save_artifact` count as read only. The greeting uses the workspace timezone: morning 05:00–11:59, afternoon 12:00–17:59, evening 18:00–04:59. The jobs chart buckets by hour in the workspace timezone. A job counts as "waited for a person" when its run entered `waiting_approval` or `waiting_input` in that hour. Cancelled jobs count with failed ones. Paused and running jobs form a fourth series, "in progress" |
| **D15. Pull-request base** | If the base branch's head moved after approval, the connector stops with `base_moved`. A new approval shows the diff against the new head. What was approved is exactly what gets opened |
| **D16. New run key** | ⇧⌘O, since browsers keep ⌘N for a new window. This amends D3 and SH-02 |
| **D17. Seed** | The coordinator drafts the seed definitions in PRD-Studio SD-02 from the concepts, and the owner reviews them. An Expert whose tool is unavailable is seeded without that tool and says so in its purpose. Interview synthesis is seeded as a draft until a workflow execution can carry files |
| **D13. Later** | The model-assisted features stay out of EPIC-15: suggested tools for a new Expert, and "Generate from a run". Each needs its own plan, caps and consent text |

## What this gives up

- **DS-02's single dark default for everyone.** A person who picks System gets light whenever their Mac is light.
- **A narrower GitHub blast radius.** A token that can write contents and open pull requests can change the repository's branches. The approval, branch naming and path limits contain this, but don't make it impossible.
- **Decision 0013's clean metrics boundary.** A few local numbers now appear. Anything more needs another decision.

## What this doesn't establish

That any of this is built, works live against GitHub, or meets H1 or product acceptance.

## Reversal

Each D-row reverses on its own. D2 needs DS-02 restored and the spec reverted. D6 and D7 need the tools removed from the registry, which makes them `not_registered`. D8 can discard drafts without touching published versions.
