# PRD addition: Studio product surfaces

**Status:** approved by the owner on 2026-11-07, through [Decision 0022](../engineering/decisions/0022-studio-product-surfaces.md).

**Extends:**
- [PRD-LangChain-Deep-Agents.md](PRD-LangChain-Deep-Agents.md): §7.3 (workflows), §9 (tools), §11.3 (events) and §12.1 (screens).
- [PRD-Tool-Catalog.md](PRD-Tool-Catalog.md).
- [PRD-Design-System.md](PRD-Design-System.md).

**Derived from:** [the Studio features plan](../plan/studio-features.md) and the nine [Studio concepts](../imagine/README.md).

Every earlier requirement still applies unless Decision 0022 amends it:
- OpenRouter is the only inference provider.
- Approval covers one exact request.
- Estimated and reported costs stay distinct.
- Terminal runs can't resume.
- Secrets never reach the browser or evidence.
- State is never shown by color alone.

The concepts' sample data is illustrative. Each screen shows only real data.

## Shell

**SH-01. Sidebar.** The links are grouped into the work group (Home, Runs, Approvals), **Build** (Experts, Workflows, Tools) and **System** (Operations, Models, Settings). The skip link stays the first tab stop.

**SH-02. Shortcuts.** ⇧⌘O opens Home's composer with focus in the goal. ⌘K opens search (SR-01). Both are buttons in the shell, after the skip link, with visible key hints. Neither acts while focus is in a text field.

**SH-03. Approvals badge.** The Approvals link shows the number of pending approvals in the workspace, in words for assistive technology ("2 waiting"). It comes from a count endpoint, not from a listed page.

**SH-04. Health line.** A line shows "All local services ready", or names the first service that isn't ready. It comes from a member-readable readiness read that returns no counts or paths.

**SH-05. Account.** The footer shows the display name (ID-01), the role in the current workspace and "this Mac". Its menu offers Settings → Account and Sign out.

## Identity

**ID-01. Display name.** Each user has an editable profile name, from 1 to 60 characters, protected by RLS: a user edits their own, and members of a shared workspace read it. Without one, the part of the sign-in email before `@` is used.

**ID-02. Session.** The session summary returns the user's role and the name of each workspace.

## Home

**HM-01. Greeting.** "Good morning", "Good afternoon" or "Good evening", by the workspace's timezone, followed by the display name. The heading is "What should we work on?". The boundaries are in Decision 0022 D14.

**HM-02. Composer chips.**
- An **Expert** chip picks no Expert (a goal run), or one Expert. With one, it starts a direct session before admission.
- A **budget** chip picks from US$0.25 to US$5.00 in steps of US$0.25, default US$1.00, and never above the remaining daily cap. The disclosure updates with the choice.
- A **models** chip opens the run's model choice.
- Attached files show as chips with name, type and size.

**HM-03. What the run would use.** Under the disclosure, chips show the profiles the roles resolve to ("Terra · 13 roles", "Sol · researcher"), and the tools the run would be granted, from a preview endpoint. Nothing is sent until Run.

**HM-04. Needs you and recent runs.**
- **Needs you** lists pending approvals, linking to Review, and runs `waiting_input`, linking to Reply on the run.
- **Recent runs** lists the five newest, with state, progress or spend, and relative time.

**HM-05. Service chips.** Home shows the readiness of the API, worker and database (SH-04), and the OpenRouter authentication status.

## Runs

**RN-01. List projection.** Each row returns:
- goal summary, and the Expert, session or workflow label;
- status and `stop_reason`;
- plan progress (tasks complete of total);
- the frozen profiles;
- spend: charged, outstanding reservations and an unreported flag;
- created and updated times.

**RN-02. Filters.**
- Tabs **All**, **Active** (queued, running, verifying, paused, cancelling), **Needs you** (`waiting_approval`, `waiting_input`) and **Finished** (succeeded, failed, cancelled), each with a server count.
- A text filter over goal and Expert name, and a profile filter.
- Keyset cursor pagination, with "Load more" and a total.

**RN-03. Spend display.** A row shows "≈" before an amount while reservations are outstanding or a charge is unreported, and the reported amount after. A meter shows spent and reserved of the frozen limit.

**RN-04. Side panel.** Selecting a row opens a panel with:
- the state badge, title, Expert and start time;
- the plan with done, current and to-do markers, each with its tools and its wall time;
- spend, tokens and "N of 20 metered tool calls" for the root run tree;
- Open run, Pause, Resume and Cancel, with the expected-version guard.

**RN-05. Task timing.** The worker records each plan task's start and finish times on the fenced write path. The current task is the earliest open task that has started.

## Experts

**EX-01. Card facts.** A card shows the executor binding's role and profile, the granted tools (first four, then +N), a run count, the time of the last run, and Start run.

**EX-02. Filters.** **All**, **Can change things outside** (any granted tool whose class is consequential) and **Read only** (no consequential tool), each with a count, plus text search.

**EX-03. Approval note.** A card whose tools include one that needs approval on every call says so ("Approval on every issue").

## Approvals

**AP-01. Inbox.** Two tabs with counts: **Waiting** (pending) and **Decided** (approved, rejected, expired, withdrawn). A list sits beside the selected request's detail, and J and K move between requests.

**AP-02. Facts.** Requested by, the run's goal, the plan task it serves (through the tool use with the same operation ID), and the expiry as relative and absolute time. Decided requests also show who decided, when, and the outcome.

**AP-03. Exact request.** The full stored arguments, with the hash and byte size. A **Fields** view (parsed keys in a definition list, markdown shown as text and also rendered and sanitized) and a **JSON** view. Neither hides, reorders or truncates content. A request too long to show whole still can't be approved.

**AP-04. Shortcuts.** ⌘↵ approves and ⌘⌫ rejects the focused request. Each needs a second press within 2 s, which the screen announces. Neither acts while focus is in a text field.

## Operations

**OP-01. Verdict.** The readiness sentence, "N of M checks pass", the worker count and the hold state.

**OP-02. Check detail.** Each check shows its value when one exists:
- database answer time, as the p95 of the last 20 probes;
- applied migrations;
- storage bytes;
- disk free and total (numbers only);
- leased and queued jobs;
- the checkpoint adapter;
- the catalog's fetch time;
- a loopback-only bind check.

**OP-03. Jobs chart.** Jobs per hour over 24 hours, in the workspace timezone, split into succeeded, waited for a person, failed (including cancelled) and in progress, as Decision 0022 D14 defines them, with a text table as its alternative.

**OP-04. Existing sections.** Delayed schedules, backups, restores, tracing, model routes and retention stay.

## Workflows

**WF-01. List.** Name, description, the Experts it uses ("Research analyst → Brief writer"), the published version and any draft, the number of steps, the last execution's state and time, and a run count. Tabs **All**, **Published** and **Drafts**, plus search.

**WF-02. Drafts.**
- A workflow may hold one saved draft graph, editable by the owner.
- Publishing from it checks the expected version and creates the next immutable version.
- Discarding it leaves published versions untouched.
- Runs and routines bind only published versions.

**WF-03. Preview panel.** The selected version's steps in order. Each agent step shows its label, Expert, model and granted tools. The approval gate is marked. A version switch toggles between published and draft.

**WF-04. Executions.** Recent executions with version, state, spend (estimated or reported) and duration.

**WF-05. Budget.** An execution takes a budget from US$0.25 to US$5.00, frozen on its run.

**WF-06. Labels and description.** A workflow has an optional description. Graph nodes gain an optional `label`, which bumps the IR version, and older versions stay valid.

## Tools

**TL-01. Layout.** A group list with counts, a text filter, and the existing provider and availability filters. Selecting a row opens its detail in a side panel, which is a modal dialog since [Decision 0026](../engineering/decisions/0026-cronjob-tool-and-tool-guide.md) G2 (PRD-Tool-Catalog TG-02). The `/tools/{tool_id}` page stays as the deep link.

**TL-02. Granted to.** The detail lists the Experts whose latest version grants the tool, and the published workflows that reach it through their Experts.

**TL-03. Copy schema.** A button copies the input JSON Schema.

## GitHub tools

All of these use one configured repository (`GITHUB_REPOSITORY`) and one `GITHUB_TOKEN`. Both resolve per workspace by [Decision 0025](../engineering/decisions/0025-keys-and-vars.md): the value saved at Settings → Keys & vars, then the worker's environment, then `.env`. They apply under the TC and TU requirements, the URL guard and fake-transport tests. No input names a repository.

**GH-01. `github_list_pull_requests`.** Read only. Inputs: state (`open`, `closed` or `merged`), base branch, a since date, and a limit of up to 100. Outputs: number, title, author login, merged time, labels and URL.

**GH-02. `github_list_workflow_runs`.** Read only. Inputs: workflow file name, branch, status (`failure` or `success`), since, limit. Outputs: run ID, conclusion, times, head SHA, and failing job and step names.

**GH-03. `github_search_issues`.** Read only. Inputs: query text and state. The search is restricted to the repository. Outputs: number, title, state, labels and URL.

**GH-04. `github_read_file`.** Read only. Inputs: path and ref. Text up to 1 MiB. Outputs: content, SHA and size; the content is never public on run screens.

**GH-05. `create_github_issue` version 2.** Adds optional `labels`, up to 10. Version 1 stays as it is.

**GH-06. `github_open_pull_request`.** Consequential, with approval on every call.
- Inputs: title, body, base branch, and a list of file changes (path and full new content, up to 20 files and 1 MiB in total).
- The approval shows each file's diff against the base.
- The connector creates the branch `autobots/<operation_id>`, commits only the named paths, and opens the PR with the operation ID as a marker in its body.
- A retry reads back the branch and PR first, and returns an existing PR.
- If the base branch's head moved after approval, it stops with `base_moved`, and a new approval is needed (Decision 0022 D15).
- Merging is not offered.

**GH-07. Keys.** Availability is `key_missing` until both variables are set. The repair names them, the token's scopes, and a restart, or saving them at Settings → Keys & vars (Decision 0025).

## Seed

**SD-01. Concept Experts and workflows.** A repeatable seed creates seven Experts and seven workflows in a chosen workspace, with no secrets and no pending jobs. It is separate from migrations. The Experts are Market watcher, Research analyst, Brief writer, Issue triager, Code maintainer, by [Decision 0032](../engineering/decisions/0032-google-search-through-serpapi.md) G8, Google bot and, by [Decision 0034](../engineering/decisions/0034-deep-research-like-content-writer.md) E1, Deep research writer. The workflows are Weekly competitor brief, Monthly FX and inflation note, Nightly test triage, Interview synthesis, Release notes from merged PRs, Vendor due diligence and, by Decision 0034 F1, Deep research content writer. A workflow whose tools are unavailable is seeded as a draft.

**SD-02. Seed definitions.** Drafted by the coordinator from the concepts for the owner's review (Decision 0022 D17). Role bindings follow the workspace policy unless named.

| Expert | Purpose | Tools |
|---|---|---|
| Market watcher | Tracks prices, exchange rates and inflation, and explains what moved and why it matters | `market_history`, `inflation_rates`, `calculate`, `read_csv`, `save_artifact`, `publish_artifact` |
| Research analyst | Searches the web and reads sources carefully. Cites every claim and flags anything it couldn't confirm | `search_web`, `extract_website_content`, `tavily_search`, `tavily_extract`, `save_artifact`, `publish_artifact` |
| Brief writer | Turns findings into a short brief with a recommendation, a comparison table and numbered sources | `read_run_file`, `save_artifact`, `publish_artifact` |
| Issue triager | Groups failing checks by cause and drafts one GitHub issue per distinct failure. Each issue waits for you | `read_csv`, `github_list_workflow_runs`, `github_search_issues`, `create_github_issue` |
| Code maintainer | Reads the repository, edits copies in the run's files, and proposes a pull request that waits for you | `github_read_file`, `search_files`, `read_code_file`, `patch_code_file`, `write_code_file`, `github_open_pull_request` |
| Google bot | Searches Google through SerpApi for up to 30 ranked results, reads the most relevant pages and cites each source (Decision 0032 G8) | `google_search`, `google_map`, `google_extract`, `google_crawl`, `save_artifact`, `publish_artifact` (Decision 0033 K8) |
| Deep research writer | Researches a topic the way Deep-Research-Content-Writer does: up to 30 Google results, the best pages read and numbered as sources, and one cited document of 2,000 to 3,000 words with references (Decision 0034 E1, with its instructions, E3 and E4) | `google_search`, `google_extract`, `search_web`, `extract_website_content`, `read_artifact`, `read_run_file`, `save_artifact`, `publish_artifact` |

| Workflow | Steps (agent steps name their Expert) | Seeded as |
|---|---|---|
| Weekly competitor brief | input (competitors, question) → Gather sources (Research analyst) → Compare plans and prices (Research analyst) → Write the brief (Brief writer) → approval → output | published |
| Monthly FX and inflation note | input (pairs, countries) → Pull rates and inflation (Market watcher) → Write the note (Brief writer) → output | published |
| Nightly test triage | input (workflow file, branch) → Find failures and duplicates (Issue triager) → approval → File one issue per failure (Issue triager) → output | published when the GitHub tools are available, otherwise a draft |
| Interview synthesis | input (question) → read (attached notes) → Synthesize themes (Brief writer) → output | draft until executions can carry files |
| Release notes from merged PRs | input (since, base branch) → Collect merged PRs (Code maintainer) → Write the notes (Brief writer) → approval → output | published when the GitHub tools are available, otherwise a draft |
| Vendor due diligence | input (vendors, criteria) → foreach vendor: Research the vendor (Research analyst) → join → Compare and recommend (Brief writer) → approval → output | published |
| Deep research content writer | input (topic, reader's goal) → Research and write (Deep research writer) → Check and report (Deep research writer, as its reviewer) → approval → output | published when `google_search` is available, otherwise a draft (Decision 0034 F2) |

## Search

**SR-01. ⌘K.** One endpoint searches runs (by goal), Experts, workflows and tools by name. It returns typed results limited to the workspace. The palette is a dialog with a listbox, full keyboard support and focus returned on close.

## Settings

**SE-02. Sub-navigation.** Appearance, Notifications, Account, Data on this Mac and Keyboard, plus links to Models and Operations.

**SE-03. Appearance.**
- Theme: **System**, **Light** or **Dark** (DS-02 as amended).
- Serif for documents: on by default.
- Density: Comfortable or Compact.
- Stream text as it's written.
- Reduce motion: follows the OS, and can be forced on.

All are stored in the browser and change presentation only.

**SE-04. Account.** Display name (ID-01), email (read-only), role, and Sign out.

**SE-05. Notifications.** "Tell me when a run waits for me": browser notifications for runs entering `waiting_approval` or `waiting_input` while the app is open, with the browser's permission. Nothing is pushed off the Mac.

**SE-06. Data on this Mac.** Read-only summary of retention, with a link to Operations for the owner.

**SE-07. Keyboard.** A list of the shortcuts.

## Models

**MD-01. Catalog facts.** For each approved profile: input and output price per 1M tokens from the catalog, the supported parameters shown as capabilities (labelled "from the catalog", separate from qualification), and the catalog's fetch time.

**MD-02. Binding source.** Each role's binding says whether it comes from a run override, a workspace override, the workspace default, or the built-in default (for example, `researcher` → Sol).

**MD-03. Form actions.** Discard returns the form to its saved state. Reset all clears the role overrides with the expected version. The summary reads "N of 14 roles follow the workspace default".

## Streaming

**ST-01. Result text.** While the final result is written, the API may emit ephemeral, coalesced `result.text.delta` events with the text only. Durable events and the stored artifact are authoritative. Reconnect rebuilds from the artifact. No reasoning, tool argument or raw framework value is ever streamed.
