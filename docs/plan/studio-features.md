# Plan: make the app work like the Studio concepts

**Date:** 2026-11-07. **Status:** the owner answered section 8 on 2026-11-07 (see [Owner answers](#owner-answers)). Still not a requirement source: the next step is `PRD-Studio.md` and a decision recording these answers.

The owner asked for the app to look **and work** like the nine [Studio concepts](../imagine/README.md), and for the tools that the concepts' Experts and workflows need. [Decision 0021](../engineering/decisions/0021-studio-interface-redesign.md) already gave every screen the Studio look, as a presentation-only change. Its R6 set aside everything that needs data or behavior the app doesn't have. This plan covers that remainder.

Like the [tool-catalog plan](tool-catalog.md), it follows the repository's route:

1. The owner answers [section 8](#8-decisions-for-the-owner) and [section 7](#7-external-setup-you-would-do).
2. A PRD records the result as `PRD-Studio.md`, and decisions settle the conflicts.
3. `autobots-spec-ingest` turns that PRD into **EPIC-15** in `SPECS.md`.
4. The stories are delivered one by one with `/ohmyorch:deliver`.

## Contents

1. [What already works](#1-what-already-works)
2. [What's missing, screen by screen](#2-whats-missing-screen-by-screen)
3. [Backend work, in dependency order](#3-backend-work-in-dependency-order)
4. [Tools for the concepts' Experts and workflows](#4-tools-for-the-concepts-experts-and-workflows)
5. [Where the concepts conflict with current rules](#5-where-the-concepts-conflict-with-current-rules)
6. [Phasing](#6-phasing)
7. [External setup you would do](#7-external-setup-you-would-do)
8. [Decisions for the owner](#8-decisions-for-the-owner)
9. [Draft EPIC-15 outline](#9-draft-epic-15-outline)

## 1. What already works

These are restyled already, and need no backend work:

- the grouped sidebar;
- the goal composer, with file chips, workspace models and the disclosure;
- run Pause and Cancel;
- Expert cards and the coordinator dock;
- approval facts and the exact-request Approve or Reject;
- Operations' readiness, check cards, queue, model routes and retention form;
- the workflow approval block and Run for a version;
- the tool catalog and tool detail;
- the Light and Dark theme cards;
- OpenRouter key, authentication and profile qualification, and role overrides.

## 2. What's missing, screen by screen

Status codes: **D** means the data exists but the UI doesn't show it. **B** means backend work is needed (SQL, Python, API, generated client, BFF). **C** means it conflicts with a rule (see section 5).

| Screen | Missing | Kind |
|---|---|---|
| Sidebar | ⌘K search across runs, Experts, workflows and tools | B (X12) |
| | Approvals count badge | D, plus a count field |
| | "All local services ready" health line | B (X2: a member-readable readiness) |
| | Account footer: name, role and menu | B (X1) |
| | ⌘N "New run" | C (keyboard rule) |
| Home | Greeting with your name | B (X1) |
| | Expert chip | D (direct session, then admit) |
| | Budget chip | D, plus a decision on the range |
| | "Terra · 13 roles" chips | D |
| | Tools the run would use | B (X11) |
| | Needs you: approvals | D |
| | Needs you: questions waiting for input | B (X3) |
| | Recent runs with progress and spend | B (X3) |
| Runs | All / Active / Needs you / Finished tabs with counts | B (X3) |
| | Text and model filters | B (X3) |
| | Expert, session or workflow subtitle | B (X3) |
| | "Failed · tool budget" and "Running · 3 of 5" | B (X3) |
| | Models column | B (X3) |
| | Spend, with ≈ while estimated | B (X3) |
| | Load more | B (X3, a cursor) |
| | Side panel: plan, spend meter, tokens, Pause and Cancel | D |
| | Side panel: "now" step and per-step time | B (X4) |
| | "3 of 20 metered tool calls" | B (X4) |
| Experts | Role and model line | D, plus which binding to show |
| | "Can change things outside" and "Read only" filters | D |
| | Search | UI |
| | "12 runs · last today" | B (X6) |
| | Start run on each card | D |
| | "We'll suggest tools and a role" | Decision: a new paid model call |
| Approvals | Waiting and Decided tabs with counts | B (X5) |
| | Run goal and "For task" | B (X5) |
| | Decided time | B (X5) |
| | Request size beside the hash | B (X5) |
| | Fields and JSON views | D |
| | Keyboard shortcuts | Decision |
| | "Rejected · run replanned" | Decision: no such link exists |
| Operations | "8 of 8 checks pass" | D |
| | Worker count, migration count, storage and disk bytes, catalog time, loopback check | B (X10) |
| | Jobs chart for the last 24 h | B (X10), plus a decision against Decision 0013 |
| | p95 latency | C (metrics are deferred) |
| | Runbook link | Decision |
| Workflows | All / Published / Drafts, and "v4 draft beside v3 published" | B (X8), plus a decision |
| | Last execution, run count, recent executions with spend and duration | B (X7) |
| | Description and step labels | B (X7) |
| | Step preview: Expert, model and tools | D |
| | Per-execution budget | B (X8), plus a decision |
| | "Generate from a run" | Decision: a new paid model call |
| Tools | Group list with counts | D |
| | Text filter | UI |
| | Side panel instead of a page | UI |
| | "Granted to" Experts and workflows | D |
| | Copy schema | UI |
| Settings | Sub-navigation: Account, Data on this Mac, Keyboard, Notifications | B / Decision |
| | Serif, density and reduce-motion choices | Decision (browser-only) |
| | "Stream text as it's written" | C (no text deltas, SP-011) |
| | System theme | C (DS-02) |
| Models | Capability chips, prices per 1M, catalog fetch time | B (X9) |
| | "Built-in default" source | B (X9) |
| | Discard, Reset all, "13 of 14 follow default" | UI |

## 3. Backend work, in dependency order

Each item is one or more stories. Each layer stays separate: SQL owns the schema, and Pydantic/OpenAPI owns the API. The TypeScript client is regenerated in the same change, and the BFF checks session and workspace.

| # | Work | Layers | Touches |
|---|---|---|---|
| X1 | **Identity:** role and workspace name in `SessionSummary`, and a display name (from the email, or a new profile column) | SQL + RLS, API, client, BFF | US-2.3, SP-009 |
| X2 | **Member readiness:** `ready` and `openrouter` for members, without the owner-only counts | API, client | US-9.1, US-11.8, SP-018 |
| X3 | **Run list v2:** Expert, session and workflow labels; frozen profiles; plan progress; `stop_reason`; ledger spend (charged, outstanding, unreported); status-group filter and counts; text filter; cursor | Python projection, API, client | US-11.5, US-4.6, SP-010, MP-07, LC-24 |
| X4 | **Run timing:** current task, task start and finish times (written on the fenced worker path), root-tree metered-call counter | SQL, worker, API | US-4.3, US-4.6, Decision 0017 Q4 |
| X5 | **Approvals:** decided statuses and counts, `decided_at`/`decided_by`, run goal, task title (via `tool_uses.operation_id`), stored argument size | Python, API | US-5.3, US-11.7, Decision 0015 |
| X6 | **Expert usage:** run count and last run | Python, API | US-5.1 |
| X7 | **Workflow read models:** executions per workflow with status, version, spend and duration; description; node labels (an IR version bump) | SQL, Python, API | US-6.1, US-6.3, PRD 7.3 |
| X8 | **Workflow drafts and budgets:** a saved draft beside the published versions (publish from draft with an expected version; runs bind only published versions); a spend limit per execution | SQL + RLS, Python, API | PRD 7.3, US-6.3 |
| X9 | **Model catalog facts:** pricing, supported parameters, catalog fetch time, binding source | Python, API | US-11.6, MP-02, MP-04, Decision 0019 |
| X10 | **Operations detail:** worker count, migration count, storage and disk bytes (numbers only, never paths), catalog time, loopback check; then, if approved, a query counting jobs per hour | Python, API | US-9.1, SP-018, Decision 0013 |
| X11 | **Composer preview:** the default goal tool grants in `checkRunIntent`, and the allowed budget range | Python, API | US-11.9, US-3.3, MP-07 |
| X12 | **⌘K search:** one endpoint over runs, Experts, workflows and tools | Python, API, client, UI | after X3, X6 and X7 |

## 4. Tools for the concepts' Experts and workflows

The concepts use five Experts and six workflows. Workflows call tools only through an `agent` node's Expert, and the `approval` block is the gate.

| Concept | Tools it needs | Status |
|---|---|---|
| Market watcher | `market_history`, `inflation_rates`, `calculate`, `read_csv`, `save_artifact` | All exist |
| Research analyst | `search_web`, `extract_website_content` (Jina), `tavily_*`, `browse_goal` | Exist. They need `JINA_API_KEY` and `TAVILY_API_KEY` |
| Brief writer | `save_artifact`, `publish_artifact`, `read_run_file` | All exist |
| Issue triager | `read_csv`, `create_github_issue` | Exist |
| | Duplicate check | **New:** `github_search_issues` |
| | Read failing CI | **New:** `github_list_workflow_runs` |
| Code maintainer | `search_files`, `read_code_file`, `patch_code_file` (run files only) | Exist |
| | Read the real repository | **New:** `github_read_file` |
| Weekly competitor brief | The tools above, plus the approval gate | Buildable now. A schedule needs routines, which are later scope (Decision 0009) |
| Monthly FX and inflation note | Market tools | Buildable now |
| Nightly test triage | `github_list_workflow_runs`, `github_search_issues`, `create_github_issue` | Needs the new tools |
| Interview synthesis | `read_run_file` on attached inputs | Needs execution inputs to carry files (see X7) |
| Release notes from merged PRs | **New:** `github_list_pull_requests` | Needs the new tool |
| Vendor due diligence | A coordinator with the research tools | Buildable now |

**Proposed new tools.** All are GitHub, for one configured repository only.

| Tool | Class | Network | Approval | Provider charge |
|---|---|---|---|---|
| `github_list_pull_requests` | read-only | leaves this Mac | none | none |
| `github_list_workflow_runs` | read-only | leaves this Mac | none | none |
| `github_search_issues` | read-only | leaves this Mac | none | none |
| `github_read_file` | read-only | leaves this Mac | none | none |

Each one:

- uses the existing catalog, the tool-use record and the URL guard;
- reads the same `GITHUB_REPOSITORY`/`GITHUB_TOKEN` pair;
- accepts no repository argument from the model;
- is tested on a fake transport, under Decision 0017 C5.

**Not proposed here: opening pull requests.** The concept's "Patch README" would need it. That is a second consequential connector, with approval on every call. It also has a weaker idempotency story than issues ([Decision 0007](../engineering/decisions/0007-first-connector-github-issues.md)). It should get its own decision if you want it.

**Seed content.** An optional local seed can create the five concept Experts and six workflows in your workspace, as repeatable seeds kept separate from migrations. It would hold no secrets and no pending jobs.

## 5. Where the concepts conflict with current rules

| Concept | Rule | Options |
|---|---|---|
| System theme | DS-02 offers only Dark and Light | Keep the rule, or amend DS-02 |
| Tools under Build | Decision 0017 C9 places Tools directly before Settings | Keep the rule, or amend C9 and `tools.spec.ts` |
| ⌘N "New run" before Home | `appearance.spec.ts`: Home is the first stop after the skip link | Put the shortcut after the nav, or keyboard-only |
| "Stream text as it's written" | SP-011: public events carry no text deltas | Drop it |
| p95 latency on Operations | Metrics are deferred (Decision 0013) | Drop it, or open metrics scope |
| Jobs chart | The same deferral, though counting jobs isn't timing | Decide |
| Repository and labels as approval fields | Decision 0007: repository is configuration; the tool takes title and body | Keep the rule, or add labels to the tool's input |
| Retention 30 days vs 7 days | The validator requires retry keys ≥ run days | The concept's numbers are just wrong |

## 6. Phasing

| Phase | Stories | Needs |
|---|---|---|
| **A. Data the UI can already have** | All the D rows: approvals badge, Expert chip, model chips, Expert filters, Fields/JSON, tool group counts, Granted to, "8 of 8", Discard/Reset, and the run side panel from the existing workspace | Nothing external |
| **B. Read models** | X1, X2, X3, X5, X6, X9, X11 | Nothing external |
| **C. Workflow depth** | X7, X8 | Drafts decision |
| **D. GitHub read tools** | Four tools, plus the Issue-triager and release-notes workflows | Your GitHub token (section 7) |
| **E. Run timing and Operations detail** | X4, X10 | Jobs chart decision |
| **F. Search and preferences** | X12, Settings sub-pages, density, serif, reduce motion | Their decisions |
| **G. Model-assisted features** | Suggested tools for a new Expert; "Generate from a run" | Paid-call authority and budgets |

## 7. External setup you would do

Nothing here is needed for phases A to C.

| Service | What you'd do | For |
|---|---|---|
| **GitHub** | Choose one repository. Create a fine-grained token for **that repository only**, with Issues read and write, Pull requests read, Actions read, Contents read, and Metadata read. Put it in the worker environment as `GITHUB_REPOSITORY` and `GITHUB_TOKEN`, then restart the worker and API. Use a throwaway private repository for qualification. | Phase D. This widens Decision 0007, which limits the token to issues |
| **Tavily** | Optional `TAVILY_API_KEY` | `tavily_*` tools |
| **Jina** | `JINA_API_KEY` | `search_web`, `extract_website_content` |
| **OpenRouter** | Nothing new | Already configured |
| **Paid calls** | Explicit authority and a cap for any live qualification of the new tools, and for phase G's model calls | Decision 0017 C5 keeps everything on fakes otherwise |

## 8. Decisions for the owner

1. Which rules give way to the concepts (section 5)?
2. GitHub: widen to the four read tools on one repository, keep issues only, or skip it?
3. Workflow drafts: persist drafts beside published versions, or keep publish-only?
4. "Needs you" means `waiting_approval` plus `waiting_input`. Does `paused` count too?
5. Display name: derive it from your sign-in email, or add a profile name field?
6. Budget chip range on Home, and per workflow execution (for example US$0.25–5.00, within the daily cap).
7. The jobs chart: build it as a count, with a text alternative, or drop it?
8. Phase G: approve paid model calls for suggesting Expert tools and generating workflows, now or later?

### Owner answers

Given on 2026-11-07, in this session.

| # | Question | Answer | Consequence |
|---|---|---|---|
| 1 | Conflicts in section 5 | **The concepts win** | Amend DS-02 to add a System theme. Amend Decision 0017 C9 to put Tools under Build, and update `tools.spec.ts`. Open a narrow metrics scope for the jobs chart and per-check detail; p95 latency needs a measurement source. Streaming text needs a public text-delta event, which amends SP-011: result text only, never private reasoning. The approval shortcuts, ⌘N and ⌘K are built with focus and confirmation safeguards. The retention example stays bound by the validator |
| 2 | GitHub | **Read tools, plus approval-gated pull requests** | Four read-only tools and a second consequential connector, `github_open_pull_request`, which needs approval on every call. It needs an idempotency design (a branch name derived from the operation ID, read back before a retry). This widens Decision 0007 |
| 3 | Workflow drafts | **Persist drafts** | X8 as planned. Runs bind only published versions |
| 4 | "Needs you" | **`waiting_approval` and `waiting_input`** | `paused` counts as Active |
| 5 | Display name | **An editable profile field**, falling back to the part of the email before `@` | X1 adds a profile column with RLS, and Settings → Account |
| 6 | Budget range | **US$0.25–5.00**, default US$1.00, in steps of 0.25, never above the daily cap | X11 and X8 |
| 7 | Jobs chart | Built, under answer 1 | It needs an accessible text alternative |
| 8 | Paid model features | **Later** | Phase G waits for its own plan, caps and consent text |
| — | Repository | **`josoroma/bot-test`** | Built and tested on fakes first. The owner creates the token later (section 7) |

## 9. Draft EPIC-15 outline

*EPIC-15: Studio product surfaces.* Stories, one per row of section 6, each citing PRD-Studio anchors once that PRD exists:

- US-15.1 Run list v2
- US-15.2 Run side panel and timing
- US-15.3 Approvals inbox
- US-15.4 Expert usage and filters
- US-15.5 Workflow read models
- US-15.6 Workflow drafts
- US-15.7 Model catalog facts
- US-15.8 Operations detail
- US-15.9 Identity and account
- US-15.10 Member readiness and sidebar
- US-15.11 Composer preview and budget
- US-15.12 GitHub read tools (External: token)
- US-15.17 GitHub pull-request connector, approval on every call (External: token)
- US-15.18 Streaming result text (amends SP-011)
- US-15.13 Concept Experts and workflows seed
- US-15.14 Search
- US-15.15 Appearance preferences
- US-15.16 Model-assisted Expert and workflow drafting (External: paid-call authority)
