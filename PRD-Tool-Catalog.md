# PRD addition: tool catalog, tool-use record and Tools screen

**Status:** approved by the owner on 2026-11-07, through [Decision 0017](docs/engineering/decisions/0017-tool-catalog.md). **Extends:** [PRD-LangChain-Deep-Agents.md](PRD-LangChain-Deep-Agents.md) §9 (tools), §11.3 (events) and §12.1 (screens). **Derived from:** [the tool-catalog plan](docs/plan/tool-catalog.md), sections 5 to 9, with the decision's answers applied. Where this document and the plan differ, this document holds.

Everything in PRD §9 still applies: grants pin versions, discovery never grants, effects need receipts, consequential effects need approval, arbitrary execution stays disabled, and OpenRouter is the only inference provider.

## Catalog contract

**TC-01. One registry, two views.** The catalog is derived from the tool registry, never kept as a second list. Every registered `(tool_id, version)` appears exactly once and nothing else does, apart from descriptors the decision lists as planned and unavailable, which are marked `disabled_by_policy` and are never registered. A test asserts parity.

- The **developer and screen view** lists every catalogued tool and version, granted or not, with its availability in this install.
- The **agent view** stays the registry's scope-filtered catalog: granted tools only. Discovery never grants, and a model can't reach the developer view.

**TC-02. Descriptor.** Each `(tool_id, version)` has a descriptor with: `tool_id` (snake_case, `^[a-z][a-z0-9_]{2,63}$`), `version`, `title`, `description` (the text the model sees), `group`, `provider`, `operation_class`, `side_effects` (derived from the class), `network`, `cost_class` (`free_local` or `metered_provider`), an optional owner-maintained `cost_note`, an optional `key_requirement` naming the credential and its environment **variable name**, `approval` (`never`, `always`), `input_schema` and `output_schema` (JSON Schema from the Pydantic models), flattened `fields` (path, direction, type, required, description, constraints, public), `limits` (timeout, retries, output bytes), `grantable_to` (`goal`, `expert`, `workflow_node`, `coordinator`), and `availability` with a typed `availability_reason`.

**TC-03. Groups.** `planning`, `general`, `web_search`, `web_extraction`, `web_crawling`, `files`, `market_data`, `browsing`, `code`, `connectors`, `delegation`, `learning`. One group per tool. Providers: `autobots`, `tavily`, `jina`, `yahoo_finance`, `world_bank`, `github`, `browser_use`.

**TC-04. Availability.** `available`, `key_missing`, `disabled_by_policy` or `not_qualified`, computed per request from the worker-facing configuration and never stored. It shows whether a key is set, never its value, prefix, length or hash.

**TC-05. Endpoints.** Under `/v1`, behind the existing internal-token and session checks, reached through the BFF, readable by workspace members, returning no secret: `GET /v1/tools` (the catalog with `schema_version`, a `catalog_digest` over the sorted descriptors, `groups` and `tools`, filterable by group, availability and provider), `GET /v1/tools/{tool_id}` (every version) and `GET /v1/tools/{tool_id}/versions/{version}`. Pydantic owns the DTOs; the TypeScript client is generated from them.

**TC-06. Grants by group.** An Expert version may grant a group. The group expands to explicit `(tool_id, version)` pairs when the version is saved, and the version records both the pairs and the groups they came from. A tool added to a group later doesn't change a saved version. A grant naming an unavailable or `disabled_by_policy` tool is refused with a typed code.

## Tools screen

**TS-01.** A **Tools** entry in the sidebar, directly before Settings, opens `/tools`: tools by group, each with title, ID and version, provider, operation class, side effects, network, cost class and availability. Meaning is never carried by color alone. Filters for group, availability and provider live in the URL.

**TS-02.** `/tools/{tool_id}` shows the description, limits, approval, the key requirement by variable name, and two field tables, inputs and outputs, each with path, type, required, constraints, description and whether the field appears on run screens. The raw JSON Schema sits in a disclosure. Every registered version is listed.

**TS-03.** An unavailable tool shows its reason and its repair, such as "Set `TAVILY_API_KEY` in the worker's environment and restart the worker", or "Disabled until an isolated executor is qualified".

**TS-04.** The Expert editor picks tools from the same catalog, singly or by group, shows the expansion before saving, and refuses unavailable tools.

## Tool-use record

**TU-01.** The gateway records **every** dispatch, of every class and including denials, as one private tool-use row: run and root run, workspace, sequence in run, tool ID, version, group and provider as dispatched, the plan task it served (`task_id`, the "why"), requested and finished times by database time, outcome and typed code, the input digest, the public input and output fields, output size, the effect receipt's operation ID when there is one, provider units if reported, and the lease generation. Receipts stay the effect ledger.

**TU-02.** Writes are fenced like other worker writes: a worker that lost its lease can't record a tool use.

**TU-03.** Two event types join the public envelope with `schema_version: 1`: `tool.use.started` and `tool.use.completed`, carrying identifiers, tool, version, group, task, outcome, code, duration and operation ID only. Public fields are read from the tool-use listing, never from the stream. A consumer ignores an event type it doesn't know.

**TU-04. Redaction.** Each definition lists its public input and output fields; the default is none. URLs are stored without query string or fragment. Page text, rows and file content are never public, only their digest and size. Public projection happens after the tool's own redaction. No configured key value may appear in a row, event, receipt, checkpoint or log line, and a test scans for fake keys.

**TU-05. Access and retention.** The table is private: no PostgREST, Realtime or browser role. It is read by server SQL in a projection, and follows the workspace's retention. Child runs are listed under their root.

**TU-06. Spend.** A root run tree may make at most 20 metered tool calls. The next is denied with `tool_budget_exceeded` before any request.

**TU-07. Listings.** `GET /v1/runs/{run_id}/tool-uses` lists a run tree's uses in order, cursor-paginated, with the plan task's title.

## Tool-use views

**TV-01.** The run workspace shows **Tools used**: one row per use, in order, with time and duration, tool and group, the plan task's title, public inputs, outputs or digests, and outcome. Rows appear live from `tool.use.*` events and reload from the listing.

**TV-02.** The workflow monitor shows tool uses under the node's run.

**TV-03.** Lists use headings and table semantics, announce new rows politely, and pass axe.

## Provider keys

**PK-01.** Tool-provider keys are read from the worker's environment inside each attempt and passed to the adapter's HTTP client only. They never enter a scope, checkpoint, graph state, prompt, tool schema, event, tool-use row, receipt, log line or evidence. Tool inputs have no credential field.

| Variable | Tools |
|---|---|
| `TAVILY_API_KEY` | `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl` |
| `JINA_API_KEY` | `search_web`, `extract_website_content` |
| `GITHUB_REPOSITORY`, `GITHUB_TOKEN` | `create_github_issue` (Decision 0007, names by the owner's rename) |

**PK-02.** A missing key makes only that provider's tools `key_missing`. A run or Expert that grants an unavailable tool is refused at admission or save with a typed code; other runs are unaffected.

**PK-03.** No live key check runs automatically. Tests use fake transports even when a real key is present.

## URL guard

**UG-01.** Every URL a tool fetches, or sends to a provider to fetch, passes one guard: `https` only, no userinfo, a bounded length, a host whose DNS answers are all public (no loopback, private, link-local, carrier-grade NAT, multicast, reserved, unspecified or cloud-metadata addresses), every redirect revalidated, at most 3 redirects, a size cap and a time cap. A refusal is a typed code before any request.

## Web tools

All are `read_only`, `metered_provider`, use `httpx` through an injectable transport, enforce schema ceilings, never offer provider-side inference, and offload nothing past `max_output_bytes` (they truncate and say so).

| ID | Provider | Input → output |
|---|---|---|
| `tavily_search` | Tavily | `query`, `search_depth` (`basic`, `advanced`), `max_results` ≤ 10, `topic`, `time_range`, `include_domains`, `exclude_domains` → `results[] {title, url, content, score}` |
| `tavily_extract` | Tavily | `urls[]` ≤ 5, `extract_depth` → `results[] {url, content_markdown}`, `failed[] {url}` |
| `tavily_map` | Tavily | `url`, `max_depth` ≤ 2, `max_breadth` ≤ 20, `limit` ≤ 50 → `base_url`, `urls[]` |
| `tavily_crawl` | Tavily | Map's inputs plus `extract_depth`, `limit` ≤ 20 → `results[] {url, content_markdown}` |
| `search_web` | Jina (`s.jina.ai`) | `query`, `max_results` ≤ 10 → `results[] {title, url, snippet}` |
| `extract_website_content` | Jina (`r.jina.ai`, reader mode) | `url` → `url`, `content_markdown`, `links[]` |

Every URL passes the URL guard before it is sent. Fetched text is labelled third-party in the tool output.

## File tools

| ID | Class | Input → output |
|---|---|---|
| `read_run_file` v2 | `read_only` | `path`, `offset`, `limit` (lines) → `content`, `media_type`, `version`, `sha256`, `total_lines`, `truncated` |
| `read_csv` | `read_only` | `path`, `delimiter`, `has_header`, `max_rows` ≤ 500, `columns` → `columns[] {name, inferred_type}`, `rows`, `row_count`, `truncated` |
| `store_remote_file` | `reversible_internal_write` | `url`, `path` under `outputs/` → `path`, `version`, `sha256`, `size_bytes`, `media_type`. Through the URL guard, text types only, 1 MiB |

**FI-01. Agent File Input.** The goal composer attaches up to 5 text files (plain text, markdown, JSON, CSV), 1 MiB each, as run inputs under `inputs/`, with their media type. It isn't a catalog tool.

## Market data

| ID | Provider | Input → output |
|---|---|---|
| `market_history` | Yahoo Finance chart endpoint | `symbols[]` ≤ 5, pattern `^[A-Z0-9.^=-]{1,20}$`, `period` (`5d`, `1mo`, `3mo`, `6mo`, `1y`), `interval` (`1d`, `1wk`) → per symbol `rows[] {date, open, high, low, close, volume, pct_change}`, `currency`, `source`, `retrieved_at` |
| `inflation_rates` | World Bank Indicators API | `countries[]` from `CRI`, `USA`, `EMU`, `start_year`, `end_year` → per country `rows[] {year, inflation_pct}`, `indicator: FP.CPI.TOTL.ZG`, `source` |

`pct_change` is the close-to-close percent change computed by the tool; its first row is null. Failures are typed: `symbol_not_found`, `provider_unavailable`, `rate_limited`. Both are `read_only`; neither needs a key, and both count as metered calls under TU-06 because they leave the Mac.

## Code tools

Over the run's own files only, pure Python, no shell and no binary.

| ID | Class | Input → output |
|---|---|---|
| `search_files` | `read_only` | `pattern` (regex), `target` (`content`, `files`), `path` prefix, `file_glob`, `output_mode` (`content`, `files_only`, `count`), `context` ≤ 5, `limit` ≤ 200, `offset` → `matches[] {path, line_number, content}` or `files[]`, `total_count`, `truncated` |
| `read_code_file` | `read_only` | `path`, `offset`, `limit` → numbered `lines`, `total_lines`, `truncated` |
| `write_code_file` | `reversible_internal_write` | `path` under `outputs/`, `content` → `path`, `version`, `sha256` |
| `patch_code_file` | `reversible_internal_write` | `path` under `outputs/`, `old_string`, `new_string`, `replace_all` → `path`, `version`, `sha256`, `replacements` |

A match line is capped at 500 characters. A pattern that doesn't compile is `invalid_pattern`. A patch whose `old_string` is absent, or ambiguous without `replace_all`, fails with a typed code and writes nothing.

## Isolated browser executor

By [Decision 0018](docs/engineering/decisions/0018-browser-executor.md) B1 to B3.

**BX-01. Container.** One disposable container per browsing call, from the official Playwright image pinned by digest: non-root, all capabilities dropped, `no-new-privileges`, a read-only root, a 256 MiB `tmpfs` for profile and cache, and no bind mount, volume or Docker socket. Its environment holds nothing of the worker's: no model or provider key, no database URL. Caps: 1 CPU, 1 GiB memory, 256 processes, 300 seconds.

**BX-02. Network.** The container sits on an internal network whose only way out is an egress proxy. Its CDP port is published on `127.0.0.1` only, on a random port, behind a per-session token.

**BX-03. Egress proxy.** A sidecar applies the URL guard to every request the browser makes, subresources, redirects and WebSocket upgrades included: `https` only, every DNS answer public, and a connection to the address it checked, so a rebinding name can't reach a private address. It refuses loopback, private, link-local, carrier-grade NAT, metadata and multicast destinations, caps bytes and requests per call, and refuses non-`GET` requests that carry a body. It logs hosts, not paths or queries.

**BX-04. Ownership.** An executor belongs to one attempt. Losing the lease, cancelling the run, or reaching the time cap closes the CDP session and removes the containers. Containers are labelled with the run and generation, and a sweeper removes any a crashed worker left.

**BX-05. Qualification.** The executor reports qualified only after a live check on a disposable stack shows every refusal: the API's and Supabase's loopback ports, the Docker host, a private address, the metadata address, a public name resolving to loopback, a `file://` URL, a download, the memory and process caps, and removal after a cancel.

## Admitted browser model

By Decision 0018 B4 and B7.

**BM-01.** browser-use's agent loop runs in the worker. Its model is an adapter implementing browser-use's chat-model protocol, and each call is an admitted call of the run: a reservation, an invocation ticket and receipt, the run's frozen `researcher` route on an approved OpenRouter profile, the shared transport, and settled spend. Uncertain outcomes follow the existing rules.

**BM-02.** browser-use's own model clients are never constructed. A model call outside the adapter fails as unadmitted, and an exhausted budget refuses the call before it is sent.

**BM-03.** browser-use's typed actions are requested as the route's structured output where the route enforces it; otherwise the call is refused with a typed code before it is sent.

**BM-04.** `browser-use` is pinned in `uv.lock`, and the adapter is tested offline against that version's protocol with a scripted model.

## Autonomous browsing

`browse_goal` (browser-use) stays `disabled_by_policy` and unregistered until the isolated browser executor is qualified and the admitted browser model exists (Decision 0017 C3 and C4). Then, by Decision 0018 B5 and B6:

| Input | Constraint |
|---|---|
| `task` | 1 to 2000 characters |
| `start_url` | A guarded `https` URL |
| `allowed_domains` | 1 to 10 domains; navigation outside them is refused for that call |
| `max_steps` | 1 to 20, default 10 |
| `max_seconds` | 10 to 300, default 120 |

Output: `summary` (labelled third-party, cut to the shared text budget), `visited` (URLs without query or fragment), `steps`, `model_calls`, and `stopped` (`done`, `max_steps`, `max_seconds`, `refused_action` or `cancelled`). Public fields: `start_url`, `allowed_domains`, `max_steps`, `stopped`, `steps` and the count of visited URLs, never the summary or page text.

**AB-01.** It reads only: navigate, click links, scroll, read and extract. Typing, form submission, sign-in, upload and download are not in its action set, and the egress proxy refuses a submission that gets through.

**AB-02.** It stays `arbitrary_execution`. The registry admits that class only for a tool whose executor reports qualified. It is granted only through an Expert, every call waits for a person's approval, it counts as one metered call, and each of its steps counts as the run's model spend.
