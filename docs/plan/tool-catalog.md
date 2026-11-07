# Plan: tool catalog, tool-use record and Tools page

**Date:** 2026-11-07. **Status:** proposal only. Nothing here is implemented, approved or in `SPECS.md`.

This plan is not a requirement source. `AGENTS.md` and `.claude/rules/delivery.md` say backlog intent comes from approved PRDs and owner decisions, ingested through `autobots-spec-ingest`. `CODEBASE.md` describes what exists, not what should exist. So the EPIC drafted in [section 12](#12-draft-epic-in-specs-style) is input for a PRD addition. It is not a backlog edit.

## Contents

1. [What is being asked](#1-what-is-being-asked)
2. [Recommended path, and why not edit SPECS.md directly](#2-recommended-path-and-why-not-edit-specsmd-directly)
3. [What exists today](#3-what-exists-today)
4. [Conflicts with existing rules](#4-conflicts-with-existing-rules)
5. [Tool catalog contract](#5-tool-catalog-contract)
6. [Requested tools, mapped to the contract](#6-requested-tools-mapped-to-the-contract)
7. [Tool-use record and events](#7-tool-use-record-and-events)
8. [Provider keys](#8-provider-keys)
9. [Web: the Tools page and tool use on run and flow screens](#9-web-the-tools-page-and-tool-use-on-run-and-flow-screens)
10. [Phasing and dependencies](#10-phasing-and-dependencies)
11. [Risks](#11-risks)
12. [Draft EPIC in SPECS style](#12-draft-epic-in-specs-style)
13. [Open questions](#13-open-questions)

## 1. What is being asked

The request has two parts.

1. **A Tools page** in the web app, placed before Settings in `NAVIGATION` in [`sidebar-nav.tsx`](../../apps/web/components/sidebar-nav.tsx). It shows each tool's inputs, outputs and types. The detail must be fine enough that reports, Experts and workflows can grant tools one at a time or as a group.
2. **A discovery API** for agents and developers. Run and flow views use the same API to show which tools a run used, when, why, and for what.

The requested tools, by group:

| Group | Tools |
|---|---|
| Web search | Search The Web (built-in), Tavily Search |
| Website extraction | Tavily Extract, Extract Website Content (built-in): extracting links, visiting them, converting pages to markdown |
| Web crawling | Tavily Crawl, Tavily Map |
| Files | Agent File Input, File Read, File Store, Read CSV |
| Market data | yfinance: crypto (`BTC-USD`, `ETH-USD`) and FX to Costa Rican colón, daily history and percent change. Inflation for Costa Rica, the USA and Europe was also asked about |
| Autonomous browsing | browser-use |
| Code | `search_files` (ripgrep-backed, modelled on Hermes Agent), with `read_file`, `patch`, `write_file` |

Provider keys listed for `.env.example`: `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `AUTOBOTS_GITHUB_ISSUES_REPOSITORY`, `AUTOBOTS_GITHUB_ISSUES_TOKEN`, `JINA_API_KEY`.

## 2. Recommended path, and why not edit SPECS.md directly

The brief asked to "add a new EPIC to SPECS.md". This plan proposes a different route.

1. **Write a PRD addition**, either a new `PRD-Tool-Catalog.md` or a new section of `PRD-LangChain-Deep-Agents.md` §9. Base it on sections 5 to 9 of this plan. The owner approves it, and registers it in `.claude/autobots.json` `documents` if it is a new file.
2. **Record decisions** under `docs/engineering/decisions/` for the points no source settles. These include tool providers versus the OpenRouter-only rule, paid tool calls, the arbitrary-execution class and browser-use's model use. [Section 4](#4-conflicts-with-existing-rules) lists them, and Decision 0007 is the precedent for a connector decision.
3. **Run `autobots-spec-ingest`.** Its read-only ingestor returns the new EPIC with `Source:` lines that point at the PRD and decision anchors. The coordinator persists it, then runs `python3.12 scripts/specs.py render` and `validate`.
4. **Deliver story by story** with `/ohmyorch:deliver`, under `.claude/rules/ohmyorch-delivery.md`.

**Why this order.**

- `AGENTS.md` says to "preserve source requirements" and "not infer new requirements from code". `scripts/specs.py validate` checks that each story's `Source:` links resolve. A hand-written EPIC would cite this plan, which is not an approved source, or cite nothing.
- `.claude/rules/ohmyorch-delivery.md` says to stop on "a decision its sources do not make". Most stories below hit one: paid calls, live keys, a new provider class, arbitrary execution. Without a PRD and decisions, `/ohmyorch:deliver` would stop on its first story.
- `promote` moves a story to `READY` only when it has no open question and no `External:` dependency. The draft stories carry both, on purpose, until the owner answers [section 13](#13-open-questions).
- Decision 0014 says that "nothing here authorizes a paid call or a persistent change", and that Decision 0013's authority for those has ended. Any live Tavily, Jina or Yahoo call needs new owner authority, which a PRD and decision can give.

**Scope changes this plan recommends.** Some parts of the request would drift from the current contract.

- **Catalog first, providers later.** The catalog, the tool-use record and the Tools page can be built and checked over the eight tools that exist today, with no keys and no paid calls. That work is useful alone, and later provider tools only add rows to it.
- **One provider at a time**, each behind its own decision and fake transport, like GitHub in Decision 0007.
- **browser-use stays deferred.** It is an agent with its own model loop and broad browser actions. PRD 9.1 classifies that as arbitrary execution, which `ToolRegistry.register` refuses today. It needs an isolated executor and a decision on its model calls first.
- **Code tools work on run files, not the host.** PRD 9.3 says to "prefer a small explicit tool set and virtual run files". A ripgrep tool on the host's real filesystem would need the isolated executor too.
- **Inflation needs a source other than yfinance.** See [section 6.5](#65-market-data).

## 3. What exists today

From `CODEBASE.md` (analyzed revision `4315944`) and the files cited here. These are facts the plan builds on, not requirements.

- **Registry.** `ToolDefinition` in [`application/tool_gateway.py`](../../services/agent/src/autobots/application/tool_gateway.py) already holds most of what a catalog entry needs: `tool_id`, `version`, `description`, `input_model`, `output_model` (Pydantic), `operation_class`, `timeout_seconds`, `retries`, `max_output_bytes`, `approval_required`, `resource_target`, `resources`, `reconcile`, `safe_to_repeat` and `redact`. `ToolRegistry.catalog(scope)` returns only granted tools, with name, version, description and input schema, for the model.
- **Classes.** `OperationClass` in [`domain/tools.py`](../../services/agent/src/autobots/domain/tools.py) has `pure`, `read_only`, `reversible_internal_write`, `consequential_external_write` and `arbitrary_execution`. `ToolRegistry.register` refuses `arbitrary_execution` "until an executor is qualified", and refuses retries on effectful tools.
- **Tools.** `propose_plan`, `complete_task`, `read_offload` (plan tools), `calculate`, `read_run_file`, `save_artifact`, `publish_artifact`, `search_memory`, plus optional `propose_improvement` and `create_github_issue`, and `assign_specialist` for coordinator runs. Grants pin a version, and anything ungranted is denied (`ToolScope`).
- **Receipts.** Only effectful tools write `app_private.tool_receipts`. A read "has no effect, so no receipt" (`ToolGateway._read`). So today **no durable record exists of a read-only or pure tool call**, apart from the `tool_dispatches` counter in run usage.
- **Events.** `public.run_events` stores `payload jsonb` with `schema_version`. The typed union `RunEvent.payload` in [`contracts/runs.py`](../../services/agent/src/autobots/contracts/runs.py) has six members: `run.status_changed`, `artifact.published`, `artifact.missing`, `approval.requested`, `approval.decided`, `effect.reconciled`. No tool-use event exists. PRD 11.3's example uses `tool.operation.completed`.
- **Inspector.** `run_projection.py` reads `tool_receipts` into `tool_attempts`, and states that it never reads "checkpoint content, tool arguments or partial model output". `run-inspector.tsx` shows a "Tool operations" card.
- **SDK tools hidden.** `adapters/tool_middleware.py` filters by name the file, shell and subagent tools that Deep Agents attaches, keeping only names in `scope.tools`. `goal_loop.py` leaves "skills, memory, subagents and a backend" unset.
- **Run inputs.** Admission writes text input documents into `app_private.run_files` as `text/plain` under `inputs/`. `RUN_FILE_GRANTS` is `("inputs", "outputs")`.
- **Connector credential.** `create_github_issue` reads its repository and token from the worker's environment for each attempt and never stores them (Decision 0007). OpenRouter keys are AES-256-GCM sealed in `app_private` (`application/credentials/`).
- **Contracts.** `scripts/generate_contracts.py` writes `contracts/generated/openapi.json` and `packages/api-client/src/generated.ts` offline. The `full` profile checks drift.
- **Keys in the working tree.** `.env.example` at `HEAD` (commit `90aa967`) already lists `TAVILY_API_KEY` and `JINA_API_KEY`, and nothing under `services/` or `apps/` reads them. An uncommitted change renames `AUTOBOTS_GITHUB_ISSUES_REPOSITORY` and `AUTOBOTS_GITHUB_ISSUES_TOKEN` to `GITHUB_REPOSITORY` and `GITHUB_TOKEN`, in `.env.example`, `adapters/github_issues.py` and the operations runbook. See conflict C8.

## 4. Conflicts with existing rules

Each row needs an owner decision before the stories that depend on it can leave `BLOCKED`.

| # | Rule and source | What the request needs | Proposed resolution, for decision |
|---|---|---|---|
| C1 | "All application model calls use the two approved OpenRouter profiles… No… alternative provider" (`AGENTS.md`). "OpenRouter is the only inference provider" (PRD §1, option-b-contract). | Tavily, Jina and Yahoo Finance as external services. | They are **tool providers**: HTTP data services the worker calls as tools, not model providers. PRD §2.3 already allows that "permissioned web research or connector calls remain tools executed by the local worker". A decision should say so explicitly and name each tool provider, as Decision 0007 did for GitHub. |
| C2 | Same rule, applied to model inference inside a tool provider. | Tavily Search's `include_answer` returns "an LLM-generated answer" (Tavily API reference). Tavily Crawl and Map may accept natural-language instructions (to be confirmed). Jina has model-based reader options (to be confirmed). | Treat any option that runs a model on the provider's side as **inference by another provider**, and forbid it: the tool schema doesn't offer it, and the adapter sends it as off. Opening it later would need its own decision. |
| C3 | PRD 9.1: arbitrary execution, a "shell or browser action with broad capabilities", is "disabled until isolated executor and policy are qualified". `ToolRegistry.register` enforces that. | browser-use. | Keep it disabled. A browser-use story waits for an isolated-executor story and a decision. |
| C4 | `AdmittedModel` refuses any model call outside an admitted dispatch. Budgets, reservations and receipts apply to every call (`.claude/rules/model-gateway.md`). | browser-use runs its own model loop. | Any model call it makes must go through the shared gateway, on an approved profile, under the run's reservations, with invocation receipts. Whether browser-use can take an injected, admitted client is unknown (Q9). If it can't, browser-use can't be adopted under the current rule. |
| C5 | Decision 0014: authority for paid calls has ended. `AGENTS.md`: "performing paid model qualification" is not authorized by harness work. | Tavily credits, Jina usage, live key checks. | Default tests use fake transports, as for models. Each live provider qualification is its own bounded task, with an owner-set spend cap and a decision. Tool spend is not model spend, so the ledger needs a decision too (Q4). |
| C6 | PRD 9.1: "Validate destination URLs after redirects, reject loopback/private-metadata access for general web-fetch tools… bound download sizes." | File Store, the raw fetch mode of Extract Website Content, and crawled links. | Any tool that fetches a URL itself shares one URL guard: scheme allowlist, DNS resolution checked against private and loopback ranges, redirect revalidation, size and time caps. When a provider fetches the URL, the guard still checks the URL before sending it. |
| C7 | PRD 9.3: `FilesystemBackend` "is not a security sandbox"; "prefer… virtual run files". `tool_middleware.py` removes the SDK's own `read_file`, `write_file`, `edit_file`, `grep`, `glob` and `ls` by name. | `search_files`, `read_file`, `patch`, `write_file`. | Phase one runs over the run's virtual files only. **Don't reuse the SDK's names:** the middleware filters by name, so a granted `read_file` could let the SDK's own tool of that name through. Use distinct IDs (section 6.7). Real-repository code tools wait for the isolated executor (C3). |
| C8 | Decision 0007 and the committed code name `AUTOBOTS_GITHUB_ISSUES_REPOSITORY` and `AUTOBOTS_GITHUB_ISSUES_TOKEN`. | The user's list uses those names. The uncommitted working tree renames them to `GITHUB_REPOSITORY` and `GITHUB_TOKEN`. | Keep the `AUTOBOTS_`-prefixed names. A bare `GITHUB_TOKEN` is the name GitHub's own tools and CI read, so a developer's broader token could be picked up by the worker without anyone choosing it. Decision 0007 asks for a token "limited to that repository's issues". This plan changes nothing. The rename is someone else's uncommitted work (Q12). |
| C9 | PRD 12.1 lists the required screens. Decision 0009 sets the release's screen scope. | A new Tools screen. | It is an addition to §12.1 in the PRD addition, not something to infer. |
| C10 | `run_projection.py` and SP-011 never expose tool arguments or partial output. Durable events are sanitized and typed. | "Inputs and outputs" shown for each tool use. | Show only fields the tool's definition marks public, plus digests and sizes. Anything else stays private or unrecorded. Section 7 has the detail. |
| C11 | PRD §1 and Yahoo's terms. The yfinance docs say it uses "Yahoo's publicly available APIs", that the API is "intended for personal use only", and that yfinance is "not affiliated, endorsed, or vetted by Yahoo, Inc." | Market data. | Fits a single-owner local install. The decision should record the terms and that there is no SLA (Q7). |
| C12 | `.claude/rules/ohmyorch-delivery.md`: dependency installs only when a story needs them, repo-local, pinned and recorded. | New Python packages: `tavily-python` or plain HTTP, `yfinance` (pulls in `pandas`), `browser-use` (pulls in Playwright and more), a pinned `rg` binary. | Prefer plain `httpx` adapters for Tavily and Jina: a small surface, easy to fake, no extra SDK. Each package is added by the story that needs it, through `uv.lock`. |

## 5. Tool catalog contract

Pydantic owns these DTOs in `services/agent/src/autobots/contracts/tools.py`. `scripts/generate_contracts.py write` emits them into OpenAPI and the TypeScript client, so the web consumes generated types only. A `domain/tool_catalog.py` holds the pure vocabulary (groups, cost classes), separate from the DTOs, per `.claude/rules/python-worker.md`.

### 5.1 One registry, two views

The catalog is **derived from `ToolRegistry`**, not kept as a second list. Each `ToolDefinition` gains the descriptive fields below. A harness test asserts that every registered tool has a catalog entry and the reverse.

- **The developer and UI view** (`GET /v1/tools`) lists every registered tool and version, granted or not, with its availability in this install.
- **The agent view** stays `ToolRegistry.catalog(scope)`: granted tools only, injected by the loop. PRD 9.1 says "tool discovery does not imply permission to execute". A model can't call the developer API to widen its own grants.

### 5.2 Fields

`ToolDescriptor`, one per `(tool_id, version)`:

| Field | Type | Source and meaning |
|---|---|---|
| `tool_id` | `str`, snake_case, `^[a-z][a-z0-9_]{2,63}$` | Stable. Existing IDs are snake_case (`create_github_issue`), so new ones are too, rather than PRD 11.3's dotted `web.fetch` example. |
| `version` | `int ≥ 1` | As registered. Grants pin it. |
| `title` | `str` | A display name such as "Tavily Search". |
| `description` | `str` | The text the model also sees. |
| `group` | `ToolGroup` enum | `planning`, `general`, `web_search`, `web_extraction`, `web_crawling`, `files`, `market_data`, `browsing`, `code`, `connectors`, `delegation`, `learning`. One group per tool. |
| `provider` | `ToolProvider` enum | `autobots` (in-process), `tavily`, `jina`, `yahoo_finance`, `github`, `browser_use`. The internal name of whoever serves the call. |
| `operation_class` | `OperationClass` | Existing enum. |
| `side_effects` | `SideEffect` enum | `none`, `internal_write`, `external_write`, `arbitrary`. Derived from `operation_class` for display. |
| `network` | `bool` | Whether a call leaves this Mac. |
| `cost_class` | `CostClass` enum | `free_local`, `metered_provider` (credits or per call), `model_inference` (only if a decision ever allows it, C2/C4). |
| `cost_note` | `str \| None` | Owner-maintained text, such as "1 credit at basic depth, 2 at advanced". Never a computed price. |
| `key_requirement` | `KeyRequirement \| None` | `{credential: "tavily", variable: "TAVILY_API_KEY", source: "environment" \| "app_managed"}`. The variable's **name**, never its value. |
| `approval` | `"never" \| "always" \| "policy"` | From `approval_required` and policy. |
| `input_schema` | JSON Schema (object) | `input_model.model_json_schema()`, as the model sees it. |
| `output_schema` | JSON Schema (object) | `output_model.model_json_schema()`. |
| `fields` | `list[FieldDescriptor]` | Flattened for the UI and for reports: `path`, `direction` (`input`/`output`), `type`, `required`, `description`, `constraints` (enum, min/max, pattern), `public` (bool, section 7.3). |
| `limits` | `{timeout_seconds, retries, max_output_bytes}` | From the definition. |
| `grantable_to` | `list["goal" \| "expert" \| "workflow_node" \| "coordinator"]` | Where a grant may name it. `assign_specialist` is `coordinator` only, as today. |
| `availability` | `ToolAvailability` | `available`, `key_missing`, `key_invalid`, `disabled_by_policy` (for example arbitrary execution), `not_qualified`. Computed per request and never cached into durable state. |
| `availability_reason` | typed code \| `None` | Such as `tavily_key_missing`. A typed code, like other errors. |

`ToolGroupDescriptor`: `group`, `title`, `description`, `tool_ids` (current versions).

### 5.3 Endpoints

All under `/v1`, behind the existing `X-Autobots-Internal` and JWT checks, reached through the BFF. Members of the workspace can read them. None returns a secret.

| Method and path | Returns |
|---|---|
| `GET /v1/tools` | `ToolCatalog`: `schema_version`, `catalog_digest` (sha256 of the sorted descriptors, so a report can cite exactly which catalog it used), `groups[]`, `tools[]` (latest version of each). Filters: `group`, `availability`, `provider`. |
| `GET /v1/tools/{tool_id}` | Every registered version of one tool. |
| `GET /v1/tools/{tool_id}/versions/{version}` | One `ToolDescriptor`. |
| `GET /v1/runs/{run_id}/tool-uses` | `ToolUseList` for the run and its descendants, cursor-paginated (section 7). |
| `GET /v1/workflow-executions/{id}/tool-uses` | The same, grouped by node instance. |

Discovery is read-only, so no idempotency receipts are needed.

### 5.4 Grants by group

"Granular enough to use tools singly or in groups" means a grant can name a group. Grants stay explicit and pinned: **a group grant expands to explicit `(tool_id, version)` pairs when the Expert version, workflow version or goal is saved**. Immutable versions then never change meaning when a tool is later added to a group. The saved record keeps both the expansion and the group it came from, for display.

## 6. Requested tools, mapped to the contract

The proposed IDs are open to review. "Phase" refers to [section 10](#10-phasing-and-dependencies).

### 6.1 Web search

| ID | Title | Provider | Class | Key | Cost | Input → output (summary) | Phase |
|---|---|---|---|---|---|---|---|
| `search_web` | Search The Web | `jina` (`s.jina.ai`) | `read_only` | `JINA_API_KEY` | metered | `query`, `max_results` → `results[] {title, url, snippet}` | P4 |
| `tavily_search` | Tavily Search | `tavily` | `read_only` | `TAVILY_API_KEY` | metered: 1 credit basic, 2 advanced | `query`, `search_depth` (`basic`, `advanced`), `max_results`, `topic`, `time_range`, `include_domains`, `exclude_domains` → `results[] {title, url, content, score, published_date}`, `request_id` | P3 |

"Built-in" in the request appears to mean AutoGPT's blocks of these names. AutoGPT's `SearchTheWebBlock` calls `https://s.jina.ai/{query}`, and its `ExtractWebsiteContentBlock` calls `https://r.jina.ai/{url}`, both with a Jina bearer key (AutoGPT `backend/blocks/jina/search.py`). That is where `JINA_API_KEY` fits. The research PRD's authority is "a source-grounded capability reference… not automatically a clone requirement", so the owner confirms this reading (Q2).

`tavily_search` doesn't offer `include_answer`, `auto_parameters` or `include_raw_content` (C2, and `auto_parameters` can raise the depth to the 2-credit tier).

### 6.2 Website extraction

| ID | Title | Provider | Class | Key | Input → output | Phase |
|---|---|---|---|---|---|---|
| `tavily_extract` | Tavily Extract | `tavily` | `read_only` | `TAVILY_API_KEY` | `urls[]` (bounded count), `extract_depth`, `format: "markdown"` → `results[] {url, content_markdown, links[]}`, `failed[] {url, code}` | P3 |
| `extract_website_content` | Extract Website Content | `jina` (`r.jina.ai`) | `read_only` | `JINA_API_KEY` | `url`, `include_links` → `{url, final_url, content_markdown, links[]}` | P4 |

The group "extracts links, visits them, converts to markdown". The plan splits that into tools the agent composes: an extraction returns `links[]`, the agent chooses some, and a second extraction visits them. Each visit is its own recorded tool use with its own reason. A single "follow everything" tool would hide which pages were read and why, and that is crawling (6.3).

AutoGPT's raw mode fetches the URL directly. That makes it a general web fetch, which needs the C6 guard. Phase P4 offers the reader mode only, and raw fetch waits on the guard.

Large page content is offloaded into a run file through the existing offload path (`read_offload`), not inlined past `max_output_bytes`.

### 6.3 Web crawling

| ID | Title | Provider | Class | Input → output | Phase |
|---|---|---|---|---|---|
| `tavily_map` | Tavily Map | `tavily` | `read_only` | `url`, `max_depth`, `max_breadth`, `limit`, `select_paths`, `exclude_paths` → `base_url`, `urls[]` | P3 |
| `tavily_crawl` | Tavily Crawl | `tavily` | `read_only` | Map's inputs plus `extract_depth` → `results[] {url, content_markdown}`, offloaded to a run file | P3 |

Depth, breadth and limit get hard ceilings in the schema, because a crawl's credit cost grows with pages. Natural-language instructions aren't offered (C2).

### 6.4 Files

| ID | Title | Class | Input → output | Phase |
|---|---|---|---|---|
| (not a model tool) | Agent File Input | — | An upload into a run's `inputs/` through a BFF route, before or during a run. Extends today's text-only input documents to bounded binary files in private Storage, with media type and sha256. | P5 |
| `read_run_file` (existing, new version) | File Read | `read_only` | `path` → `content` as text, `media_type`, `version`, `sha256`, `truncated`. Version 2 adds text extraction for allowed types (plain text, markdown, JSON, CSV, and maybe PDF, Q11). | P5 |
| `store_remote_file` | File Store | `reversible_internal_write` | `url`, `path` under `outputs/` → `path`, `version`, `sha256`, `size_bytes`, `media_type`. Downloads through the C6 guard with a size cap, then saves like `save_artifact`, with an operation ID and receipt. | P5 |
| `read_csv` | Read CSV | `pure` (over a granted run file) | `path`, `delimiter`, `has_header`, `max_rows`, `columns` → `columns[] {name, inferred_type}`, `rows[][]`, `row_count`, `truncated` | P5 |

Agent File Input is an action the person takes, not something the model calls. It appears in the catalog as a `files` group entry with `grantable_to: []` and a note, so the Tools page still shows it in its group. Whether it belongs in the catalog at all is Q10.

### 6.5 Market data

| ID | Title | Provider | Class | Input → output | Phase |
|---|---|---|---|---|---|
| `market_history` | Market price history | `yahoo_finance` via `yfinance` | `read_only` | `symbols[]` (pattern-checked, bounded count), `period` (enum: `5d`, `1mo`, `3mo`, `6mo`, `1y`), `interval` (enum: `1d`, `1wk`) → per symbol `rows[] {date, open, high, low, close, volume, pct_change}`, `currency`, `source_timezone` | P6 |

- **Examples.** `BTC-USD`, `ETH-USD`, and `CRC=X` (Yahoo's symbol for USD to CRC) with `period="1mo"`, `interval="1d"`. `pct_change` is the close-to-close daily percent change, computed by the tool, so the model doesn't do arithmetic over the rows. Its first row is `null`.
- **EUR to CRC.** `CRC=X` is USD to CRC only. EUR to CRC would be a different symbol, probably `EURCRC=X`, which qualification must confirm, or a cross computed from `EURUSD=X` and `CRC=X`. Q6 decides which.
- **Inflation.** yfinance's documented API covers tickers, history, market summaries, search, screens, sectors, and a `Calendars` class with `get_economic_events_calendar()`. Its docs mention no inflation or CPI series. The economic events calendar may list CPI *release events*, but its fields and country coverage aren't documented. Release events aren't an inflation series anyway. **yfinance is not a source of Costa Rican, US or euro-area inflation history as documented.** Official publishers would be: for Costa Rica, BCCR or INEC; for the USA, BLS CPI or FRED; for the euro area, Eurostat HICP. Each would be a separate tool provider with its own decision. This stays open (Q5).
- **`yfinance`** pulls in `pandas` and depends on Yahoo's unofficial endpoints, which change without notice. Tests replay recorded fixtures through a fake HTTP session, and never call Yahoo. A failed request returns typed codes such as `symbol_not_found`, `provider_unavailable` or `rate_limited`.

### 6.6 Autonomous browsing

| ID | Title | Provider | Class | Phase |
|---|---|---|---|---|
| `browse_goal` | Goal-driven browsing | `browser_use` | `arbitrary_execution` | P8, blocked |

It is registered in the catalog as a descriptor with `availability: disabled_by_policy`, so the Tools page can show it as planned and unavailable, as §2.3 asks ("accurately show unavailable capabilities"). It is never registered in `ToolRegistry` until C3 and C4 are resolved. Prerequisites: an isolated, non-privileged browser container with egress control and no inherited credentials (PRD 9.3), an admitted-model adapter, a per-step budget, cancellation into the browser session, and a decision on approvals for form submissions and logins.

### 6.7 Code tools

| ID | Title | Class | Input → output | Phase |
|---|---|---|---|---|
| `search_files` | Search files | `read_only` | `pattern`, `target` (`content` or `files`), `path`, `file_glob`, `output_mode` (`content`, `files_only`, `count`), `context`, `limit`, `offset` → `matches[] {path, line_number, content}` or `files[]`, `total_count`, `truncated`, `limit_reason` | P7 |
| `read_code_file` | Read file | `read_only` | `path`, `offset`, `limit` → numbered lines, `total_lines`, `truncated` | P7 |
| `write_code_file` | Write file | `reversible_internal_write` | `path`, `content` → `version`, `sha256` | P7 |
| `patch_code_file` | Patch file | `reversible_internal_write` | `path`, `old_string`, `new_string`, `replace_all` (or a unified diff, Q8) → `version`, `sha256`, `replacements` | P7 |

- **The Hermes model.** The fetched `tools/file_operations_search.py` implements content search with `rg` (falling back to `grep`) and file search with `rg --files` (falling back to `find`). It has pagination (`limit`, `offset`), `output_mode`, `context` lines, a 500-character cap per match line, a 60-second timeout returning partial results with `search_timeout`, and skipped-path reporting. The backend's signature defaults are `path="."`, `target="content"`, `limit=50`, `offset=0`, `output_mode="content"`, `context=0`. It needs no API key. The model-facing schema and its wording on when to prefer the tool over `grep`, `rg` or `find` in a terminal weren't in the files read, so the plan doesn't quote them (Q8).
- **When it is preferred.** Nothing found requires `search_files` on every coding request. The plan documents it as the tool to use *instead of* a terminal search, because Autobots grants no shell. Experts get it only for code-shaped work.
- **Where it searches.** Phase P7 searches the run's virtual files (`app_private.run_files`), not the host (C7). ripgrep needs a real directory, so the run's granted files are written to a fresh per-call temporary directory with no symlinks, and `rg` runs there with a fixed argument list, no shell, `--no-follow`, and time and output caps. Alternatively, a pure-Python search over the rows avoids a binary entirely. This plan recommends the pure-Python form first: it has no install and the same contract. The `rg` form follows only if size requires it.
- **Names.** Not `read_file` or `write_file` (C7).

## 7. Tool-use record and events

### 7.1 The record

A new private table, `app_private.tool_uses`, by migration. The gateway writes one row for **every** dispatch, of every class, including denials. Today only effectful calls leave a receipt. Receipts stay as they are, the effect ledger. A tool use links to its receipt by `operation_id` when there is one.

| Column | Meaning |
|---|---|
| `id` | uuid |
| `run_id`, `root_run_id`, `workspace_id` | Scope. Spend and retention follow the root. |
| `sequence_in_run` | Monotonic per run, for ordering. |
| `tool_id`, `tool_version`, `tool_group`, `provider` | Copied at dispatch, so a later catalog change doesn't rewrite history. |
| `catalog_digest` | Which catalog the run was admitted with. |
| `plan_version`, `task_id` | **Why**: the plan task the call served. The `task_id` already exists in plan contracts (`contracts/plans.py`). |
| `workflow_node_instance_id` | For flows: the node instance that called it, if any. |
| `requested_at`, `started_at`, `finished_at` | **When.** Database time, like leases. |
| `outcome` | `ToolOutcome` (`succeeded`, `failed`, `unknown`, `denied`) |
| `code` | The typed code already returned to the model. |
| `input_digest` | sha256 of the normalized arguments, the same as `_hash`. |
| `input_public` | jsonb, only the fields the definition marks public (7.3). |
| `output_public` | jsonb, the same rule for output. |
| `output_bytes`, `truncated` | Sizes. |
| `artifact_ids`, `run_file_refs` | **For what**: what the call produced or read. |
| `operation_id` | Link to `tool_receipts` for effectful tools. |
| `provider_units` | Metered units the provider reported, such as Tavily credits, if it reports them. No money unless Q4 decides. |
| `generation` | Lease generation, fenced like other writes. |

**What "why" means.** The record says *why* through the plan task: its ID, and the task's title as already stored in the run's plan. It doesn't capture the model's free-text reasoning. Today's code records "reply facts with no message content", and storing model rationale would be new durable model text. A short `purpose` argument on every tool call would be possible, but it is model-written, so it is Q3.

### 7.2 Events

Two new members of the `RunEvent.payload` union, written through `append_event` in the same transaction as the row:

```json
{ "type": "tool.use.started",   "tool_use_id": "…", "tool_id": "tavily_search", "tool_version": 1,
  "group": "web_search", "task_id": "t3" }
{ "type": "tool.use.completed", "tool_use_id": "…", "tool_id": "tavily_search", "tool_version": 1,
  "outcome": "succeeded", "code": null, "duration_ms": 812, "artifact_ids": [], "operation_id": null }
```

- These are summaries with identifiers only. The public input and output fields are fetched from `GET /v1/runs/{id}/tool-uses`, under the same membership check, so the event stream never carries tool content.
- `RunEvent` is strict. The generated TypeScript client and the SSE consumer must handle the new members before the worker emits them. Adding union members keeps `schema_version: 1` only if every consumer tolerates them, and `contract_drift` in the `full` profile will catch a stale client. The story records which (Q13).
- Per PRD 11.3, operation completion is durable. Started events are durable here too, so a reload mid-call shows the call in flight.

### 7.3 Redaction

- Each `ToolDefinition` declares `public_input_fields` and `public_output_fields` as an allowlist of JSON paths. The default is empty, so nothing is shown unless chosen.
- URLs are stored without query strings or fragments unless the tool marks them safe, because query strings can carry tokens.
- Search queries and page text are user or third-party content. They are shown to workspace members on the run's own screens, as run files are now, and fall under the workspace's retention. They are never written to logs. Whether queries count as public at all is Q3.
- `redact` already runs on output before the model or receipt sees it. The public projection is applied after `redact`, never before.
- A harness or `fast` test scans tool-use rows and events for every configured key value, using fake keys in tests, the way the US-10.2 closing checks scanned for secrets.

### 7.4 Retention and authorization

`tool_uses` is private: no PostgREST, no Realtime, no browser role. It is read by direct server SQL in a projection, like `tool_receipts`. Retention follows `retention.apply_all`, per workspace. Child runs from `assign_specialist` are included under the root, with `run_id` showing which run made the call.

## 8. Provider keys

| Variable | Used by | Holding | Check |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Model gateway only | Existing: environment, or AES-256-GCM sealed in `app_private` with configured precedence (PRD-Model-Providers) | Existing Save & validate. Unchanged by this plan. |
| `TAVILY_API_KEY` | `tavily_*` tools | Worker environment, read per attempt (the Decision 0007 pattern). App-managed sealed storage later, if the owner wants it (Q1). | Presence and format (Tavily keys appear to start with `tvly-`, to be confirmed), surfaced as tool availability. A live check costs a request, so it isn't automatic. |
| `JINA_API_KEY` | `search_web`, `extract_website_content` | The same | The same. Jina keys appear to start with `jina_`, to be confirmed. |
| `AUTOBOTS_GITHUB_ISSUES_REPOSITORY`, `AUTOBOTS_GITHUB_ISSUES_TOKEN` | `create_github_issue` | Existing (Decision 0007). Names kept (C8). | Existing configuration check. |

Rules, from PRD 9.1 and 6.7, `AGENTS.md` and the option-b contract, applied to tool keys:

- **Read inside the attempt**, from trusted runtime context, and passed to the adapter's HTTP client only. Never in a `ToolScope`, a checkpoint, graph state, a prompt, a tool schema, an event, a tool-use row, a receipt, a log line or evidence.
- **The model sees no credential references either.** Tool inputs have no credential field. The adapter knows which key it needs.
- **Availability, not the value.** `ToolDescriptor.availability` and the Operations page show `configured`, `missing` or `invalid` with a typed reason, never a prefix, length or hash of the key.
- **A missing key disables only that provider's tools.** Runs that don't need them still start. A goal or Expert that grants an unavailable tool is refused at admission with a typed code, rather than failing mid-run. That mirrors "missing credentials block inference, not local UI/files/settings".
- **Validation is explicit.** A live key check is a paid or metered call, so it happens only when the owner presses Validate, inside an authorized task. Fake transports are the test default even when a real key is present, as for models.
- **Secret scanning.** The `.claude` hook patterns and the closing-check scanner learn the Tavily and Jina key formats once confirmed. Hooks are guardrails, not confinement (`CODEBASE.md`).
- **`.env.example`.** Not changed by this plan. It already lists `TAVILY_API_KEY` and `JINA_API_KEY`. A delivery story adds comments saying which tools read each key and that each is optional.

## 9. Web: the Tools page and tool use on run and flow screens

### 9.1 Navigation

Add `{ href: "/tools", label: "Tools", icon: Wrench }` to `NAVIGATION` in [`sidebar-nav.tsx`](../../apps/web/components/sidebar-nav.tsx), directly before `/settings`. The existing longest-match rule needs no change. That file is new and uncommitted in another session's restyle, so the story waits for that work to land.

### 9.2 `/tools`

- **List.** Grouped by `group`, in catalog order. Each row shows title, `tool_id` and version, provider, operation class, side effects, network, cost class and availability. Badges use the Luma state tokens, and meaning is never carried by color alone (DS rules, Decision 0010).
- **Filters.** Group, availability and provider, kept in the URL so a view can be linked.
- **Detail** (`/tools/[toolId]`): description, limits, approval, key requirement by variable name with a link to the right Settings or Operations entry, and **two field tables** for inputs and outputs: path, type, required, constraints, description, and whether the field appears on run screens. The raw JSON Schema sits in a disclosure for developers. A version switcher lists every registered version.
- **Group detail.** The group's tools and a "grant as group" note explaining expansion (5.4).
- **Unavailable tools** show the reason and the repair: "Set `TAVILY_API_KEY` in the worker's environment and restart the worker", or "Disabled until an isolated executor is qualified".
- **Data.** Server components call the BFF, which calls `GET /v1/tools` through the generated client. No Supabase browser client is involved.

### 9.3 Grants in editors

`expert-editor.tsx`, and later the workflow editor, pick tools from the same catalog, by single tool or by group. They show the expanded list before saving, and refuse unavailable or `disabled_by_policy` tools with the same typed codes as the API.

### 9.4 Run and flow screens

- **Run workspace** (`run-workspace.tsx`): a "Tools used" section. One row per tool use, in order: time and duration (*when*), tool and group, the plan task it served with the task's title (*why*), public inputs in short form and outputs or artifacts produced (*for what*), and outcome. Rows arrive live from `tool.use.*` events and are filled from `GET /v1/runs/{id}/tool-uses`. Replay by cursor works as for other events.
- **Run inspector** (`run-inspector.tsx`): today's "Tool operations" card keeps the effect receipts. Each use links to its receipt, and from there to approvals and reconciliation where relevant.
- **Workflow monitor** (`workflow-monitor.tsx`): tool uses grouped under each node instance.
- **Report-level summary**: counts by tool and group, per run tree and per workflow execution, plus the `catalog_digest`, so a report can say exactly which tools and versions it used.
- **Accessibility**: a list or table with headings, live-region announcements for new uses, rate-limited, and keyboard-reachable disclosures. Tested with axe, as the other specs are.

## 10. Phasing and dependencies

Each phase is one or more stories, delivered through OpenSpec under the current rule. Phases P0 to P2 need no keys, paid calls or new dependencies.

| Phase | Delivers | Needs first | Live or paid? |
|---|---|---|---|
| **P0** | Catalog DTOs derived from the registry. `GET /v1/tools…`. Generated client. `/tools` page and sidebar entry over today's eight tools. Group grants with expansion. | PRD addition, and ingestion. The sidebar restyle committed. | No |
| **P1** | `app_private.tool_uses` migration. Gateway writes for every dispatch. `tool.use.*` events. Tool-use endpoints. Run workspace, inspector and monitor views. Redaction tests. | P0. A decision on "why" (Q3). | No. `db` profile on disposable targets. |
| **P2** | Tool-provider key readiness: environment reading per attempt, availability on the Tools and Operations pages, admission refusal for unavailable grants, secret-scan patterns. No provider calls. | P0. Decisions C1 and Q1. | No |
| **P3** | Tavily: `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl` as `httpx` adapters with fake transports and recorded fixtures. | P1, P2. A decision for C1, C2 and C5 naming Tavily. | Tests no. Live qualification is a separate, owner-authorized, capped task. |
| **P4** | Jina: `search_web`, `extract_website_content` (reader mode). | P1, P2. Decision, Q2. | The same |
| **P5** | Files: Agent File Input upload route, `read_run_file` v2, `read_csv`, `store_remote_file` with the URL guard. | P1. The URL guard (C6). Q10, Q11. | No |
| **P6** | Market data: `market_history`. Inflation only once a source is chosen. | P1. Decision (C11). Q5, Q6. `yfinance` pinned. | Tests no |
| **P7** | Code tools over run files: `search_files`, `read_code_file`, `patch_code_file`, `write_code_file`. | P1. C7. Q8. | No |
| **P8** | browser-use | An isolated-executor story, and decisions C3 and C4. Q9. | Yes, model calls. Blocked. |

Existing stories these depend on, by name in `SPECS.md` (all `DONE`): US-4.4 (versioned tool registry and operation receipts), US-4.6 (sanitized event replay and run workspace), US-4.3 (bounded goal planning and model/tool loop), US-5.1 and US-5.2 (Experts and specialists), US-5.3 (approvals), US-7.2 (first connector), US-3.1 (credential precedence and encrypted storage), US-2.2 (public contracts and generated types). Workflow node instances come from EPIC-6.

Each phase updates `CODEBASE.md` when it changes what that file describes, and passes `harness` before archive. Phases with SQL also run `db` on disposable targets, and web phases run `full`.

## 11. Risks

- **Spend without a ledger.** Tavily and Jina bill per call or credit, outside the model ledger. A crawl can cost many credits. Mitigations: schema ceilings on depth, breadth, limit and URL counts; a per-run `tool_dispatches` limit as today; a per-provider unit cap if Q4 adds one.
- **Prompt injection through fetched content.** Pages, search snippets and CSVs are untrusted. They reach the model as tool output, and may try to steer it toward an effectful tool. Effects already need approval when consequential, and approvals bind arguments. Fetched text should also be marked as third-party in the tool output, never merged into instructions.
- **SSRF and local exposure.** Any tool that fetches a URL itself could reach loopback Supabase (`127.0.0.1:55321`, `55322`), the API, or the metadata ranges. The C6 guard is mandatory before P5's `store_remote_file` and any raw fetch.
- **Unofficial market data.** yfinance breaks when Yahoo changes endpoints, and its terms limit it to personal use. Numbers can be wrong or late, so outputs carry the source and timestamps, and the UI labels them.
- **Event contract change.** New union members can break a strict client. Generate first, ship consumers, then emit.
- **Name collisions with SDK tools** (C7).
- **Durable third-party content.** Tool-use rows keep queries and page summaries under workspace retention. Retention and export rules must cover them.
- **Dependency weight.** `yfinance` brings `pandas`. `browser-use` brings Playwright and an agent framework. Each enlarges the lock and the review surface.
- **Scope drift.** Eleven new tools across five providers is broad for a released single-owner product, whose release record leaves the release decision open. The P0 to P2 split lets the owner stop after the catalog and record.

## 12. Draft EPIC in SPECS style

**This is a draft for the PRD addition and ingestion. It is not in `SPECS.md`.** The `Source:` lines point at the PRD sections and decisions this plan proposes. They don't exist yet, so `scripts/specs.py validate` would reject these stories until they do. The number assumes EPIC-13 is still the last epic. Every story stays `BLOCKED` until its sources exist and its open questions are answered. Phases P4 to P8 follow the same shape and are summarized in the table after the stories.

````markdown
# EPIC-14: Tool catalog and tool-use record

Post-release, after EPIC-13's scheduling. Proposed by docs/plan/tool-catalog.md; sourced from the proposed PRD-Tool-Catalog.md and its decisions. All story completion also requires SP-003/SP-021 and the OpenSpec delivery rule.

### US-14.1: Tool catalog API derived from the registry

Status: BLOCKED

As a developer or agent author
I want one versioned catalog of every registered tool with its schemas, group, provider, classes and availability
So that tools can be discovered and granted singly or by group without reading the code.

Source:
- [Proposed tool catalog contract](PRD-Tool-Catalog.md#catalog-contract) — not yet written.
- [Tool contract](PRD-LangChain-Deep-Agents.md#91-tool-contract)
- [SP-013](docs/engineering/option-b-contract.md#sp-013--tools-approvals-and-artifacts)

Acceptance Criteria:

```gherkin
Scenario: The catalog matches the registry
  Given the tools registered in this build
  When a member requests the tool catalog
  Then every registered tool and version appears once with its input and output schemas, group, provider, operation class, cost class and key requirement by name, and no unregistered tool appears

Scenario: Discovery doesn't grant
  Given a run whose scope doesn't grant a catalogued tool
  When the model is shown its tools
  Then the ungranted tool is absent and a call naming it is denied before any effect

Scenario: No secret in the catalog
  Given a provider key is configured
  When the catalog is read
  Then the response shows only the key's variable name and an availability state, never its value or any part of it
```

Dependencies:
- US-4.4
- US-2.2
- External: The owner approves the PRD addition and schedules this epic.

Tasks:
- [ ] Add descriptive fields to tool definitions and derive the catalog DTOs.
- [ ] Add the catalog endpoints and regenerate OpenAPI and the TypeScript client.
- [ ] Test registry–catalog parity and secret absence.

Open Questions:
- Q10: Does Agent File Input, which no model calls, belong in the catalog?

### US-14.2: Tools page and grants by group

Status: BLOCKED

As a workspace owner
I want a Tools page before Settings that shows each tool's inputs, outputs, types and availability, and editors that grant tools singly or by group
So that I can see what an agent may use and choose it precisely.

Source:
- [Proposed Tools screen](PRD-Tool-Catalog.md#tools-screen) — not yet written.
- [Required screens](PRD-LangChain-Deep-Agents.md#121-required-screens)
- [Design system](PRD-Design-System.md)

Acceptance Criteria:

```gherkin
Scenario: Browse tools by group
  Given the catalog holds tools in several groups
  When the owner opens Tools from the sidebar entry placed before Settings
  Then tools appear by group with their classes and availability, and a tool's detail lists every input and output field with type, required flag and constraints

Scenario: Show unavailable tools honestly
  Given a tool whose provider key is missing or whose class is disabled by policy
  When it is listed
  Then it reads as unavailable with its typed reason and repair, and an editor refuses to grant it

Scenario: A group grant stays explicit
  Given an owner grants a group to an Expert version
  When the version is saved
  Then it records the expanded tool versions and the group they came from, and a tool added to the group later doesn't change that version
```

Dependencies:
- US-14.1
- US-5.1
- External: The sidebar restyle is committed.

Tasks:
- [ ] Add the Tools list and detail pages through the BFF and generated client.
- [ ] Add group selection and expansion to the Expert editor.
- [ ] Cover the scenarios in browser specs with axe.

Open Questions:
- None beyond US-14.1's.

### US-14.3: Durable tool-use record and events

Status: BLOCKED

As a run's owner
I want every tool call recorded with when, why, what it used and produced, and its outcome
So that I can see which tools a run or flow used and for what.

Source:
- [Proposed tool-use record](PRD-Tool-Catalog.md#tool-use-record) — not yet written.
- [Public event envelope](PRD-LangChain-Deep-Agents.md#113-public-event-envelope)
- [SP-011](docs/engineering/option-b-contract.md)

Acceptance Criteria:

```gherkin
Scenario: Record every dispatch
  Given a run that calls a pure, a read-only and an effectful tool, and has one call denied
  When the calls finish
  Then each has one tool-use record with tool version, plan task, times, outcome and typed code, and the effectful one links to its receipt

Scenario: Sanitized events and views
  Given a tool whose definition marks some fields public
  When its use is streamed and listed
  Then events carry identifiers and outcome only, the listing shows only the public fields and digests, and no key value appears in rows, events or logs

Scenario: Fenced writes
  Given a worker that has lost its lease
  When it tries to record a tool use
  Then the write is refused like other fenced writes
```

Dependencies:
- US-14.1
- US-4.6
- US-4.2

Tasks:
- [ ] Add the private table by migration, and gateway writes in the dispatch transaction.
- [ ] Add the two event types to the typed union, consumers first.
- [ ] Add the tool-use endpoints, and cover the scenarios on a disposable stack.

Open Questions:
- Q3: Is "why" the plan task alone, or also a short model-written purpose? Are search queries public fields?
- Q13: Do new event members keep schema version 1?

### US-14.4: Tool use on run and flow screens

Status: BLOCKED

As a run's owner
I want the run workspace, inspector and workflow monitor to show tools used, when, why and for what
So that a run's outcome can be traced to the tools behind it.

Source:
- [Proposed tool-use views](PRD-Tool-Catalog.md#tool-use-views) — not yet written.
- [Required screens](PRD-LangChain-Deep-Agents.md#121-required-screens)

Acceptance Criteria:

```gherkin
Scenario: Live and replayed tool use
  Given a running run that calls tools
  When the owner watches it, reloads, and reconnects with a cursor
  Then each use appears once, in order, with time, tool, plan task, public inputs, outputs or artifacts and outcome

Scenario: Flow view
  Given a workflow execution whose nodes call tools
  When the monitor is opened
  Then tool uses appear under the node instance that made them
```

Dependencies:
- US-14.3
- US-14.2

Tasks:
- [ ] Add the views and live updates, and cover them in browser specs with axe.

Open Questions:
- None beyond US-14.3's.

### US-14.5: Tool-provider key readiness

Status: BLOCKED

As a workspace owner
I want each tool provider's key read server-side per attempt and shown only as available or not
So that tools work when configured and nothing leaks when they aren't.

Source:
- [Proposed provider-key handling](PRD-Tool-Catalog.md#provider-keys) — not yet written.
- [Decision 0007, credential](docs/engineering/decisions/0007-first-connector-github-issues.md#decision)
- Proposed decision: tool providers are not model providers.

Acceptance Criteria:

```gherkin
Scenario: Missing key disables only its tools
  Given no Tavily key is configured
  When a run that grants no Tavily tool is admitted, and another that grants one is requested
  Then the first is admitted and the second is refused with a typed code before any dispatch

Scenario: Key stays out of durable state
  Given a fake Tavily key is configured
  When tools run against a fake transport
  Then the value appears in no row, event, checkpoint, log line, receipt or evidence that is scanned
```

Dependencies:
- US-14.1
- US-3.1
- External: The owner's decision naming each tool provider and how its key is held.

Tasks:
- [ ] Read keys per attempt, compute availability, refuse unavailable grants at admission.
- [ ] Add the key formats to secret scanning once confirmed.

Open Questions:
- Q1: Environment only, or app-managed sealed keys as for OpenRouter?
- Q4: Is tool spend capped or ledgered, and in what unit?

### US-14.6: Tavily search, extract, map and crawl

Status: BLOCKED

As a goal's owner
I want Tavily's four operations as bounded read-only tools
So that a run can search, extract and crawl the web through one recorded path.

Source:
- [Proposed web tools](PRD-Tool-Catalog.md#web-tools) — not yet written.
- Proposed decision naming Tavily as a tool provider, with no provider-side inference.

Acceptance Criteria:

```gherkin
Scenario: Bounded calls
  Given a granted Tavily tool and a fake transport
  When the model calls it with arguments beyond a schema ceiling or with an unoffered option
  Then the call is refused before any request, and an allowed call returns validated, size-capped output recorded as a tool use

Scenario: No provider-side inference
  Given any Tavily tool call
  When its request is built
  Then options that make the provider generate an answer or follow natural-language instructions are absent or off
```

Dependencies:
- US-14.3
- US-14.5
- External: The owner authorizes and caps any live qualification separately.

Tasks:
- [ ] Add httpx adapters, schemas with ceilings, recorded fixtures and fake transports.

Open Questions:
- Do Tavily Crawl and Map take natural-language instructions in the version pinned?
````

**The rest, in brief.** Same shape, all `BLOCKED`:

| Story | Title | Depends on | Main open questions |
|---|---|---|---|
| US-14.7 | Jina Search The Web and Extract Website Content | US-14.3, US-14.5 | Q2 |
| US-14.8 | URL guard for tools that fetch | US-14.1 | none beyond C6 |
| US-14.9 | Agent File Input, File Read v2, Read CSV, File Store | US-14.3, US-14.8 | Q10, Q11 |
| US-14.10 | Market price history (yfinance) | US-14.3 | Q5, Q6, Q7 |
| US-14.11 | Code tools over run files | US-14.3 | Q8 |
| US-14.12 | Goal-driven browsing (browser-use) | US-14.3, an isolated-executor story not yet written | Q9, C3, C4 |

## 13. Open questions

Each is for the owner. None is answered here.

1. **Q1. Key storage.** Do tool keys stay in the worker's environment (Decision 0007's pattern), or get app-managed sealed storage and a Settings panel like OpenRouter?
2. **Q2. "Built-in" tools.** Do Search The Web and Extract Website Content mean the Jina-backed tools AutoGPT ships under those names? Or does "built-in" mean a no-key implementation, which would need a different backend?
3. **Q3. "Why" and public fields.** Is the plan task enough, or should each call carry a short model-written purpose stored durably? Are search queries and extracted page text shown on run screens, or only digests?
4. **Q4. Tool spend.** Are provider credits counted, capped per run or per provider, or entered into the shared ledger, and in which unit? Today the ledger counts micro-USD of model spend only.
5. **Q5. Inflation.** yfinance documents no inflation or CPI series. Which sources should supply Costa Rica, USA and euro-area inflation (BCCR or INEC, BLS or FRED, Eurostat), and is each a new tool provider decision? Is the economic events calendar wanted at all?
6. **Q6. EUR to CRC.** Use a direct Yahoo symbol (probably `EURCRC=X`, to be confirmed) or a cross from `EURUSD=X` and `CRC=X`?
7. **Q7. Yahoo terms.** Is a single-owner local install's use acceptable under "personal use only"?
8. **Q8. Code tools.** Should `search_files` and the others work on run files only (recommended), or also on a mounted repository in an isolated executor? Should `patch` take string replacement or unified diffs? The Hermes model-facing schema wasn't found in the files read. Should it be read and matched?
9. **Q9. browser-use.** Can it take an injected, admitted model client, so every call goes through OpenRouter, the reservations and receipts? Which approvals cover form submissions and sign-ins? Is an isolated-executor story wanted at all?
10. **Q10. Agent File Input.** Is it a catalog entry (an action the person takes), or only a run-input feature?
11. **Q11. File types.** Which types does File Read convert to text (PDF, DOCX, XLSX)? What size caps apply to uploads and stored files?
12. **Q12. GitHub variable names.** The uncommitted working tree renames them to `GITHUB_REPOSITORY` and `GITHUB_TOKEN`. Keep Decision 0007's `AUTOBOTS_GITHUB_ISSUES_*` names (this plan's recommendation, C8), or record a decision for the rename?
13. **Q13. Event compatibility.** Do new event types keep `schema_version: 1` with tolerant consumers, or bump it?
14. **Q14. Scope and order.** Is P0 to P2 (catalog, record, readiness, no providers) wanted as a first step that can stand alone? Where does EPIC-14 sit relative to EPIC-13, which waits for the owner?

## Sources consulted

- Repository: `AGENTS.md`, `CLAUDE.md`, `.claude/rules/*.md`, `.claude/autobots.json`, `SPECS.md` (US-7.2, EPIC-13), `PRD-LangChain-Deep-Agents.md` §2.3, §9, §11.3, §12.1, `docs/engineering/option-b-contract.md`, `CODEBASE.md`, Decisions 0007 and 0014, and the code files linked above.
- [yfinance documentation](https://ranaroussi.github.io/yfinance/), [API reference](https://ranaroussi.github.io/yfinance/reference/index.html), [`Calendars`](https://ranaroussi.github.io/yfinance/reference/api/yfinance.Calendars.html).
- [Hermes Agent `tools/file_operations_search.py`](https://github.com/NousResearch/hermes-agent/blob/main/tools/file_operations_search.py) and `tools/file_operations.py`.
- [Tavily Search API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search).
- [AutoGPT `backend/blocks/jina/search.py`](https://github.com/Significant-Gravitas/AutoGPT/blob/master/autogpt_platform/backend/backend/blocks/jina/search.py).
