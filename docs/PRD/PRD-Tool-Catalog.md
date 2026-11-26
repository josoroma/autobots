# PRD addition: tool catalog, tool-use record and Tools screen

**Status:** approved by the owner on 2026-11-07, through [Decision 0017](../engineering/decisions/0017-tool-catalog.md). **Extends:** [PRD-LangChain-Deep-Agents.md](PRD-LangChain-Deep-Agents.md) §9 (tools), §11.3 (events) and §12.1 (screens). **Derived from:** [the tool-catalog plan](../plan/tool-catalog.md), sections 5 to 9, with the decision's answers applied. Where this document and the plan differ, this document holds.

Everything in PRD §9 still applies: grants pin versions, discovery never grants, effects need receipts, consequential effects need approval, arbitrary execution stays disabled, and OpenRouter is the only inference provider.

## Catalog contract

**TC-01. One registry, two views.** The catalog is derived from the tool registry, never kept as a second list. Every registered `(tool_id, version)` appears exactly once and nothing else does, apart from descriptors the decision lists as planned and unavailable, which are marked `disabled_by_policy` and are never registered. A test asserts parity.

- The **developer and screen view** lists every catalogued tool and version, granted or not, with its availability in this install.
- The **agent view** stays the registry's scope-filtered catalog: granted tools only. Discovery never grants, and a model can't reach the developer view.

**TC-02. Descriptor.** Each `(tool_id, version)` has a descriptor with: `tool_id` (snake_case, `^[a-z][a-z0-9_]{2,63}$`), `version`, `title`, `description` (the text the model sees), `group`, `provider`, `operation_class`, `side_effects` (derived from the class), `network`, `cost_class` (`free_local` or `metered_provider`), an optional owner-maintained `cost_note`, an optional `key_requirement` naming the credential and its environment **variable name**, `approval` (`never`, `always`, `unless_yolo` for a tool whose calls wait only while the workspace's YOLO setting is off (Decision 0035 Y2), or `by_action` for a tool whose actions differ, Decision 0026 C9), `input_schema` and `output_schema` (JSON Schema from the Pydantic models), flattened `fields` (path, direction, type, required, description, constraints, public), `limits` (timeout, retries, output bytes), `grantable_to` (`goal`, `expert`, `workflow_node`, `coordinator`), and `availability` with a typed `availability_reason`.

**TC-03. Groups.** `planning`, `general`, `web_search`, `web_extraction`, `web_crawling`, `files`, `market_data`, `browsing`, `code`, `connectors`, `delegation`, `learning`, `automation` (Decision 0026), and `google` ([Decision 0033](../engineering/decisions/0033-google-toolkit-and-tool-switches.md) K1). One group per tool. Providers: `autobots`, `tavily`, `jina`, `yahoo_finance`, `github`, `serpapi` by [Decision 0032](../engineering/decisions/0032-google-search-through-serpapi.md), and `direct` by Decision 0033 K3. `world_bank` left with `inflation_rates` ([Decision 0036](../engineering/decisions/0036-inflation-rates-removed.md) R1).

**TC-04. Availability.** `available`, `key_missing`, `disabled_by_policy` or `not_qualified`, computed per request from the worker-facing configuration and never stored. It shows whether a key is set, never its value, prefix, length or hash.

**TC-05. Endpoints.** Under `/v1`, behind the existing internal-token and session checks, reached through the BFF, readable by workspace members, returning no secret: `GET /v1/tools` (the catalog with `schema_version`, a `catalog_digest` over the sorted descriptors, `groups` and `tools`, filterable by group, availability and provider), `GET /v1/tools/{tool_id}` (every version) and `GET /v1/tools/{tool_id}/versions/{version}`. Pydantic owns the DTOs; the TypeScript client is generated from them.

**TC-06. Grants by group.** An Expert version may grant a group. The group expands to explicit `(tool_id, version)` pairs when the version is saved, and the version records both the pairs and the groups they came from. A tool added to a group later doesn't change a saved version. A grant naming an unavailable or `disabled_by_policy` tool is refused with a typed code.

## Tools screen

**TS-01.** A **Tools** entry in the sidebar, directly before Settings, opens `/tools`: tools by group, each with title, ID and version, provider, operation class, side effects, network, cost class and availability. Meaning is never carried by color alone. Filters for group, availability and provider live in the URL.

**TS-02.** `/tools/{tool_id}` shows the description, limits, approval, the key requirement by variable name, and two field tables, inputs and outputs, each with path, type, required, constraints, description and whether the field appears on run screens. The raw JSON Schema sits in a disclosure. Every registered version is listed.

**TS-03.** An unavailable tool shows its reason and its repair, such as "Save a Tavily key in Settings → Keys & vars, or set `TAVILY_API_KEY` in `.env` and restart", or "Disabled until an isolated executor is qualified". An available tool that needs a key shows where its key comes from (PK-05).

**TS-04.** The Expert editor picks tools from the same catalog, singly or by group, shows the expansion before saving, and refuses unavailable tools.

## Tool-use record

**TU-01.** The gateway records **every** dispatch, of every class and including denials, as one private tool-use row: run and root run, workspace, sequence in run, tool ID, version, group and provider as dispatched, the plan task it served (`task_id`, the "why"), requested and finished times by database time, outcome and typed code, the input digest, the public input and output fields, output size, the effect receipt's operation ID when there is one, provider units if reported, and the lease generation. Receipts stay the effect ledger.

**TU-02.** Writes are fenced like other worker writes: a worker that lost its lease can't record a tool use.

**TU-03.** Two event types join the public envelope with `schema_version: 1`: `tool.use.started` and `tool.use.completed`, carrying identifiers, tool, version, group, task, outcome, code, duration and operation ID only. Public fields are read from the tool-use listing, never from the stream. A consumer ignores an event type it doesn't know.

**TU-04. Redaction.** Each definition lists its public input and output fields; the default is none. URLs are stored without query string or fragment. Page text, rows and file content are never public, only their digest and size. Public projection happens after the tool's own redaction. No configured key value may appear in a row, event, receipt, checkpoint or log line, and a test scans for fake keys.

**TU-05. Access and retention.** The table is private: no PostgREST, Realtime or browser role. It is read by server SQL in a projection, and follows the workspace's retention. Child runs are listed under their root.

**TU-06. Spend.** A root run tree may make at most 40 metered tool calls ([Decision 0034](../engineering/decisions/0034-deep-research-like-content-writer.md) L3, from 20). The next is denied with `tool_budget_exceeded` before any request.

**TU-07. Listings.** `GET /v1/runs/{run_id}/tool-uses` lists a run tree's uses in order, cursor-paginated, with the plan task's title.

## Tool-use views

**TV-01.** The run workspace shows **Tools used**: one row per use, in order, with time and duration, tool and group, the plan task's title, public inputs, outputs or digests, and outcome. Rows appear live from `tool.use.*` events and reload from the listing. A browse's row opens its steps, each with its page, screenshot and submits and, on the stealth browser, what it pressed or typed into (Decision 0035 Y11, Decision 0038 Z11).

**TV-02.** The workflow monitor shows tool uses under the node's run.

**TV-03.** Lists use headings and table semantics, announce new rows politely, and pass axe.

## Provider keys

**PK-01.** Tool-provider keys are resolved inside each attempt, from the worker's environment or, for Tavily and Jina, by PK-04's order, and passed to the adapter's HTTP client only. They never enter a scope, checkpoint, graph state, prompt, tool schema, event, tool-use row, receipt, log line or evidence. Tool inputs have no credential field.

| Variable | Tools |
|---|---|
| `TAVILY_API_KEY` | `tavily_search`, `tavily_extract`, `tavily_map`, `tavily_crawl` |
| `JINA_API_KEY` | `search_web`, `extract_website_content` |
| `SERPAPI_API_KEY` | `google_search` (Decision 0032) |
| `GITHUB_REPOSITORY`, `GITHUB_TOKEN` | `create_github_issue` and the GitHub tools of PRD-Studio (Decision 0007, names by the owner's rename; PK-07 for Settings) |

**PK-02.** A missing key makes only that provider's tools `key_missing`. A run or Expert that grants an unavailable tool is refused at admission or save with a typed code; other runs are unaffected.

**PK-03.** No live key check runs automatically. Tests use fake transports even when a real key is present.

**PK-04.** By [Decision 0024](../engineering/decisions/0024-tool-keys-from-env-and-settings.md), the Tavily and Jina keys, and the SerpApi key by Decision 0032 G7, resolve in this order, highest first: the workspace's key saved in Settings, then the process environment, then the `.env` files under the configuration root in MP-03's file order. The first non-blank value wins. Each call resolves its key inside the attempt from the run's workspace, and availability, admission and save-time checks follow the same order for that workspace.

**PK-05.** Settings → Tool keys (since PK-07, Settings → Keys & vars) lets the workspace owner save, replace or remove a Tavily or Jina key, with an expected version. The value is sealed with the master key like the OpenRouter key, and saving checks its shape only. Members see each key's source (`settings`, `environment` or none), never its value, prefix, length or hash. Removing a saved key falls back to the environment.

**PK-06.** `make start` passes `TAVILY_API_KEY`, `JINA_API_KEY` and, by Decision 0032 G7, `SERPAPI_API_KEY` from the repository's `.env` to the persistent install's API and worker. It parses the file as data, never sources it, and takes no other variable from it, except that it also passes `AUTOBOTS_BROWSER_EXECUTOR=enabled` when the file sets exactly that value (Decision 0024 K7).

**PK-07.** By [Decision 0025](../engineering/decisions/0025-keys-and-vars.md), Settings → Tool keys becomes **Settings → Keys & vars**.
- **What it holds.** It adds the GitHub token as a third secret. It also holds two values that aren't secret: the GitHub repository (`owner/name`) and the browsing switch (`enabled` or `disabled`).
- **Order.** All five follow PK-04's order for the workspace, with PK-05's owner-only, versioned save and removal. Members see a value's current value, never a secret.
- **`make start`.** It also passes `GITHUB_REPOSITORY` and `GITHUB_TOKEN` from `.env`, by PK-06's rules.
- **Per attempt.** GitHub tools resolve their repository and token per attempt from the run's workspace.

**PK-08.** A GitHub write's approval binds the repository resolved when the approval was requested. If the approved call later resolves a different repository, it is refused `approval_target_changed` before any request, and nothing is written.

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
| `google_search` | SerpApi (Google, Decision 0032) | `query`, `max_results` 1 to 30 → as `search_web` v2 (see Search paging and Google search) |

Every URL passes the URL guard before it is sent. Fetched text is labelled third-party in the tool output.

## Search paging

By [Decision 0031](../engineering/decisions/0031-search-tools-page-in-batches-of-ten.md). Version 1 of each search tool, in the table above, stays registered unchanged for grants that pinned it.

**WS-01. Search tools.** `search_web`, `tavily_search` and, by Decision 0032, `google_search`. `google_search` sits in the group `google` by Decision 0033 K1, and the other two in `web_search`. `google_map` pages the same way (Decision 0033 K2). No other tool pages.

**WS-02. Batches.** A page is 10 results, and a call requests at most 3 pages, planned as `ceil(max_results / 10)`. `search_web` v2 sends `q`, `num: 10` and `page: n` to `s.jina.ai` for each page. Tavily has no next-page request, so `tavily_search` v2 asks once for up to 20 results.

| ID | Input → output |
|---|---|
| `search_web` v2 | `query`, `max_results` 1 to 30 (default 10) → `results[] {rank, title, url, snippet}`, `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` |
| `tavily_search` v2 | Version 1's inputs with `max_results` 1 to 20 (default 10) → `results[] {rank, title, url, content, score}`, `result_count`, `pages`, `stopped`, `duplicates_removed`, `page_error` |

**WS-03. Duplicates.** Results are de-duplicated across and within pages by canonical URL (scheme and host lowercased; no fragment, `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_cid` or `mc_eid`; no trailing slash). The first occurrence is kept with its URL as given, ranks run from 1 without gaps, and the count removed is reported.

**WS-04. Stopping.** Paging stops when the call has `max_results` results (`enough`), a page is short or adds nothing new (`no_more`), the planned pages are spent (`page_limit`), or a later page fails (`provider_error`).

**WS-05. Spend.** A search call is one metered call under TU-06, admitted before its first page. Its public output records `pages`, the provider requests it made. The key is resolved once per call, and no page is retried.

**WS-06. Errors.** A first-page failure fails the call with its typed code. A later page's failure keeps the earlier pages' results, with `stopped: provider_error` and the typed code as `page_error`. Provider text never reaches the model. `search_web` v2's 70-second timeout holds three 20-second requests.

## Google search

By [Decision 0032](../engineering/decisions/0032-google-search-through-serpapi.md), G1 to G8.

**GS-01.** `google_search` v1 searches Google through SerpApi only, with `SERPAPI_API_KEY`. It never fetches or parses Google's own pages.

**GS-02.** Page n is one request with `engine=google`, `q`, `start = (n - 1) * 10`, `hl=en` and `gl=us`, under WS-02's plan and cap. Paging ends when a reply has no `serpapi_pagination.next`, not at a page with fewer than 10 results. A "Fully empty" reply is an empty page.

**GS-03.** Failures keep WS-06's rule and these codes:
- 401 or 403 is `serpapi_key_refused`;
- 429 is `rate_limited`;
- another 4xx is `provider_refused_<status>`;
- 5xx or no answer is `provider_unavailable`;
- another reply with `error` is `serpapi_search_failed`.

The key travels only in that request's query string, and no URL or provider text is kept.

**GS-04.** The SerpApi key is a Keys & vars secret by PK-04 and PK-07, and `make start` passes it by PK-06.

## Google toolkit

By [Decision 0033](../engineering/decisions/0033-google-toolkit-and-tool-switches.md), K1 to K9. It finds with Google through SerpApi, and reads pages directly from their sites.

| ID | Provider | Input → output |
|---|---|---|
| `google_search` | SerpApi | As GS-01 to GS-03; it moves to the group `google` |
| `google_map` | SerpApi | `url`, `max_results` 1 to 30 → `base_url`, `urls[]`, WS-04's paging fields. The pages Google has indexed under `site:<host><path>` |
| `google_extract` | Direct | `urls[]` 1 to 5 → `results[] {url, title, content_markdown, word_count}`, `failed[] {url, code}`, `result_count`, `truncated` |
| `google_crawl` | SerpApi, then direct | `url`, `limit` 1 to 10 → `base_url`, `google_extract`'s fields, `pages` |

**GT-01. Reading directly.** Every page and every robots.txt passes the URL guard. Each request carries the user agent `Autobots/1.0 (local research agent)`. Hosts are handled this way:
- Robots.txt is obeyed: 404 or 410 allows, and anything else that isn't a readable file denies.
- The final host after redirects is checked too.
- Requests to one host are at least a second apart, or its crawl delay up to 5 seconds.
- No page is retried.
- Only HTML and XHTML are extracted, by `trafilatura`, while plain text and markdown pass through.

A failure is a typed code, never the page's or provider's text.

**GT-02. Spend and keys.** Each call is one metered call under TU-06. `google_map` and `google_crawl` need the SerpApi key, and `google_extract` needs none.

## Tool switches

By Decision 0033, W1 to W5.

**TW-01.** The owner turns any Expert-grantable tool, or any group, on or off for the workspace on the Tools page. Everything starts on. A tool is on only while it and its group are on. The plan, delegation and workflow approval tools aren't switchable.

**TW-02.** A tool that is off reads `disabled_by_policy` with reason `turned_off` or `group_turned_off`, and its repair says where to turn it on. Then:
- admission refuses it `tool_unavailable`;
- saving an Expert refuses it `expert_tool_unavailable`;
- the gateway refuses each call to it `tool_turned_off`, before any effect.

**TW-03.** The switches live in a private table with an expected version per switch, and a stale change is refused `stale_version`. Members see the switches, and only the owner changes them.

## File tools

| ID | Class | Input → output |
|---|---|---|
| `read_run_file` v2 | `read_only` | `path`, `offset`, `limit` (lines) → `content`, `media_type`, `version`, `sha256`, `total_lines`, `truncated` |
| `read_csv` | `read_only` | `path`, `delimiter`, `has_header`, `max_rows` ≤ 500, `columns` → `columns[] {name, inferred_type}`, `rows`, `row_count`, `truncated` |
| `store_remote_file` | `reversible_internal_write` | `url`, `path` under `outputs/` → `path`, `version`, `sha256`, `size_bytes`, `media_type`. Through the URL guard, text types only, 1 MiB |
| `append_to_file` | `reversible_internal_write` | `path` under `outputs/`, `content` → `path`, `version`, `sha256`, `characters`. Adds to the end, FI-03 |

**FI-01. Agent File Input.** The goal composer attaches up to 5 text files (plain text, markdown, JSON, CSV), 1 MiB each, as run inputs under `inputs/`, with their media type. It isn't a catalog tool.

**FI-02. Reading a published artifact.** `read_artifact` reads one published artifact of the run's workspace by its ID, so a workflow's next step can read an earlier step's work ([Decision 0034](../engineering/decisions/0034-deep-research-like-content-writer.md) A1 to A4). It reads text only (markdown, plain text and JSON), in pages of lines as `read_run_file` version 2 does. It refuses `artifact_not_found` for an unknown ID, another workspace's artifact or one that isn't published, `artifact_missing` when the stored bytes are gone or fail their hash, and `artifact_not_text` otherwise. It is read-only, needs no key or approval, isn't metered, and only an Expert grants it.

**FI-03. Adding to a file.** `append_to_file` adds text to the end of a run file under `outputs/` as a new version, so a document longer than one model reply is written a section at a time ([Decision 0040](../engineering/decisions/0040-polished-transcript.md) P1, P2). A missing file is created as Markdown, and an existing one keeps its media type. The latest version is read and the next written under one lock and the run's lease. A file past 256,000 characters is refused `file_too_large`, and nothing changes. It keeps a receipt and is read back after an interruption, as `save_artifact` is. It needs no key or approval, isn't metered, and only an Expert grants it.

## Market data

| ID | Provider | Input → output |
|---|---|---|
| `market_history` | Yahoo Finance chart endpoint | `symbols[]` ≤ 5, pattern `^[A-Z0-9.^=-]{1,20}$`, `period` (`5d`, `1mo`, `3mo`, `6mo`, `1y`), `interval` (`1d`, `1wk`) → per symbol `rows[] {date, open, high, low, close, volume, pct_change}`, `currency`, `source`, `retrieved_at` |

`pct_change` is the close-to-close percent change computed by the tool; its first row is null. Failures are typed: `symbol_not_found`, `provider_unavailable`, `rate_limited`. It is `read_only`, needs no key, and counts as a metered call under TU-06 because it leaves the Mac. `inflation_rates`, on the World Bank Indicators API, is retired: a saved Expert version or routine that names it runs with its other tools, a revision drops it, and a run in flight that calls it is refused with `tool_not_registered` ([Decision 0036](../engineering/decisions/0036-inflation-rates-removed.md) R1 to R5).

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

By [Decision 0018](../engineering/decisions/0018-browser-executor.md) B1 to B3.

**BX-01. Container.** One disposable container per browsing call, from the official Playwright image pinned by digest: non-root, all capabilities dropped, `no-new-privileges`, a read-only root, a 256 MiB `tmpfs` for profile and cache, and no bind mount, volume or Docker socket. Its environment holds nothing of the worker's: no model or provider key, no database URL. Caps: 1 CPU, 1 GiB memory, 256 processes, 300 seconds. A browse on browser-use (Decision 0035 Y8, Y9) adds a third container from the same pinned image with browser-use 1.0.6 from its own lock, with the same hardening and caps, on the internal network only, and its session's time cap is 600 seconds. Each session's cap includes a 60-second grace for its start and cleanup. Downloads are also off by Chromium's managed policy. Code that turns them back on over CDP gets the download cancelled and the call ended with `refused_action`, and anything written stays in the box's `tmpfs`. An Expert set to `stealth` drives the stealth browser instead (Decision 0038 Z1, Z2): real Google Chrome, headed under Xvfb, in an image of its own from the same pinned base, with the box's policy, the workspace's time zone and a fresh profile each call. It names no user agent, device or fingerprint of its own (Z3). Its hardening and caps are the same, except 512 processes (Z4).

**BX-02. Network.** The container sits on an internal network whose only way out is an egress proxy. Its CDP port is published on `127.0.0.1` only, on a random port, behind a per-session token.

**BX-03. Egress proxy.** A sidecar applies the URL guard to every request the browser makes, subresources, redirects and WebSocket upgrades included: `https` only, every DNS answer public, and a connection to the address it checked, so a rebinding name can't reach a private address. It refuses loopback, private, link-local, carrier-grade NAT, metadata and multicast destinations, caps bytes and requests per call, and refuses non-`GET` requests that carry a body. It logs hosts, not paths or queries. A browse on browser-use, which runs only under YOLO (Decision 0035 Y5), may also submit by `POST` with a body, and send `OPTIONS`, on `https` within its domains. Every other method stays refused. A browse on browser-use and the stealth browser may also reach a fixed list of challenge hosts, `challenges.cloudflare.com`, `captcha-delivery.com` and `datadome.co` with their subdomains, as parts of a page only: the worker's guard refuses a top-frame navigation to one, which ends the call `refused_action` (Decision 0038 Z7).

**BX-04. Ownership.** An executor belongs to one attempt. Losing the lease, cancelling the run, or reaching the time cap closes the CDP session and removes the containers. Containers are labelled with the run and generation, and a sweeper removes any a crashed worker left.

**BX-05. Qualification.** The executor reports qualified only after a live check on a disposable stack shows that a `GET` to the qualification host, `https://example.com/` (Decision 0018), loads through the proxy connected to the address it checked, and shows every refusal: the API's and Supabase's loopback ports, the Docker host, a private address, the metadata address, a public name resolving to loopback, a `file://` URL, a download, the memory and process caps, and removal after a cancel. The stealth browser reports qualified only from its own live check, which observes each of these again on its image with its own cases, and only while the executor is qualified (Decision 0038 Z6).

## Admitted browser model

By Decision 0018 B4 and Decision 0020, which replaced browser-use with Autobots' own browsing loop.

**BM-01.** The browsing loop runs in the worker over the isolated browser executor. Each step shows the model the current page as text (its URL, title, a cut of its readable text and its numbered links) and is one admitted call of the run: a reservation, an invocation ticket and receipt, the run's frozen `researcher` route on an approved OpenRouter profile, the shared transport, and settled spend. Uncertain outcomes follow the existing rules.

**BM-02.** The loop has no model client of its own. A call made outside admission fails as unadmitted, and an exhausted budget refuses the call before it is sent.

**BM-03.** The model answers each step with exactly one action, as a required tool call with typed arguments: open a numbered link, go to a URL, scroll, or finish with a summary. A route whose catalog entry lacks tool support is refused with a typed code before anything is sent, and an answer that isn't one valid action ends the call.

**BM-04.** No package is added for it: the loop drives the executor over CDP with the locked `websockets` client, and it is tested offline with a scripted model.

**BM-05.** browser-use, which runs only under YOLO (Decision 0035 Y5), calls a model through a per-browse endpoint the worker serves on the Mac's loopback (Decision 0035 Y7).
- **Admitted like a loop step.** Each chat completion it sends is one admitted call of the run on its frozen `researcher` route, as BM-01 to BM-03 require of a loop step: a reservation, an invocation ticket and receipt, `model_calls` and the shared transport. The model a request names is ignored.
- **Refused before anything is sent.** A request past the run's budget, model calls or time, from a cancelled run, or carrying content the route isn't qualified for, such as an image (Y16), is refused with a typed code.
- **Reached only through the relay.** The endpoint answers only the session's token. Only the browse's egress sidecar holds it, and relays `POST /v1/chat/completions` from the box's network, so the box reaches no other part of the host and holds no key or token.

## Autonomous browsing

`browse_goal` (Autobots' browsing loop) stays `disabled_by_policy` and unregistered until the isolated browser executor is qualified and the admitted browser model exists (Decision 0017 C3 and C4). Then, by Decision 0018 B5 and B6:

| Input | Constraint |
|---|---|
| `task` | 1 to 2000 characters |
| `start_url` | A guarded `https` URL |
| `allowed_domains` | 1 to 10 domains; navigation outside them is refused for that call |
| `max_steps` | 1 to 20, default 10 |
| `max_seconds` | 10 to 300, default 120 |

Output: `summary` (labelled third-party, cut to the shared text budget), `visited` (URLs without query or fragment), `steps`, `model_calls`, and `stopped` (`done`, `max_steps`, `max_seconds`, `refused_action`, `invalid_action` or `cancelled`; `invalid_action` by Decision 0020 L6). Public fields: `start_url`, `allowed_domains`, `max_steps`, `stopped`, `steps` and the count of visited URLs, never the summary or page text.

**AB-01.** While the workspace's YOLO setting is off, it reads only: navigate, click links, scroll, read and extract. Typing, form submission, sign-in, upload and download are not in its action set, and the egress proxy refuses a submission that gets through. While YOLO is on, it runs on browser-use and may also press, type and submit by `GET` or `POST` within the call's domains (Decision 0035 Y5). The run records each form submission's host and path, never its values or query: among version 3's public fields, and with each step's screenshot in the run's private storage (Y11). On the stealth browser nothing is drawn on the page, so each step's record names instead the first ten elements it pressed or typed into, by action, kind and label and never the typed value, read from a world the page can't see (Decision 0038 Z11). There its steps are at least 2 seconds apart on either engine, and one browse of a site runs at a time across the install: another waits within its own limit or ends `max_seconds` (Z12). Nothing to sign in or pay with is in the box. Chromium's policy turns off downloads, file selection, the password manager and card and address autofill.

**AB-03.** A refused action ends the call at once with `stopped: refused_action`: a navigation outside `allowed_domains`, a typing or submission action, or a request the egress proxy refuses for an action the agent chose. Nothing more is requested and no further model step is taken; the output keeps the summary so far, the URLs visited and the steps used. A page's own subresource the proxy refuses is counted and doesn't end the call (Decision 0018). A request whose user agent isn't the browser's own is refused on both browsers: a top-frame navigation under one ends the call, and a page's own request doesn't (Decision 0038 Z13).

**AB-04. Bot checks.** On browser-use, a bot check or CAPTCHA recognised from the page itself ends the call with `stopped: bot_check` (Decision 0035 Y10, Y16). Recognised signs are reCAPTCHA's visible checkbox or challenge, an hCaptcha, Cloudflare challenge, DataDome or Arkose frame, or Google's "sorry" page. Nothing solves it, hides from it or retries around it. On the stealth browser, a check that is the page itself (Google's "sorry" page, a Cloudflare challenge on the site's own host or a DataDome frame) gets 20 seconds to clear, within the call's own limit, while the model's next request waits; one that stays ends the call `bot_check` (Decision 0038 Z8). A Turnstile frame on a page isn't a check, and a reCAPTCHA, hCaptcha or Arkose one still ends the call at first sight (Z9). browser-use is told never to press or answer one, and nothing solves one (Z10). Versions 1 and 2, which have no such stop reason, fail with the code `bot_check`.

**AB-05. Typed results.** Version 3 takes an optional `output_schema`: a JSON Schema (Draft 2020-12) object of at most 8 KB, whose top-level `x-link-fields` lists the paths of its link fields, such as `flights[].url` (Decision 0035 Y12, Y19). browser-use's result keeps its query and fragment only in those fields, and every other URL in it is bare. It is then validated against the schema, and a result that doesn't validate stops the call `invalid_action`. Visited URLs stay bare. From version 4, `save` beside the schema has the worker write the validated result straight to one of the run's files under `outputs/`, within the run's path grants: every item of one array, in order and one line each by a layout, or the whole result as JSON. The output then names the file's path, version, SHA-256, items and characters in place of the result, so the model never retypes it, and the tool row shows the path and the count (Decision 0039 V1 to V5). `not_saved` says why a finished result wasn't saved, and it comes back instead: `no_items`, `too_large` or `lease_lost` (V6).

**AB-02.** It stays `arbitrary_execution`. The registry admits that class only for a tool whose executor reports qualified. The owner's switch is resolved per workspace by PK-07, and a saved `disabled` turns it off for that workspace. It is granted only through an Expert, it counts as one metered call, and each of its steps counts as the run's model spend. While the workspace's YOLO setting is off, every call waits for a person's approval. While it is on (frozen at the run's admission and on now, Decision 0035 Y2 to Y4), a call starts without approval, and is refused before any container starts when a domain it names isn't inside its Expert's browse domains, or its Expert lists none (Y3). Its Expert's version names the browser, `box` or `stealth`, and no input does (Decision 0038 Z1). Either engine drives it (Z5). A call of a stealth Expert is refused `stealth_browser_unqualified` before any container starts while the stealth browser isn't qualified, and never runs on the box instead (Z6). Its tool row shows `browser: stealth`.

## Automation

By [Decision 0026](../engineering/decisions/0026-cronjob-tool-and-tool-guide.md), C1 to C8.

**CJ-01.** `cronjob` v1, in the group Automation, manages the workspace's routines (US-7.1) through the routine service. It takes the action `list`, `create`, `update`, `pause`, `resume`, `run` or `remove`, and it stays in the run's workspace.

**CJ-02.** `list` runs without approval. Every other action waits for a person's approval, which shows the action, the routine and its schedule. The descriptor's `approval` is `by_action` (TC-02 gains that value). The tool is granted only through an Expert.

**CJ-03.** `create` and `update` apply the routine service's validation and codes. `pause` and `resume` set `enabled`. `run` admits one occurrence now, with the scheduled path's overlap and admission rules. `remove` marks a routine removed: disabled, hidden and never evaluated, with its history kept and its name free. An action naming a removed routine is refused `routine_not_found`, and `run` on a paused routine `routine_paused`.

**CJ-04.** Its public fields are `action`, `routine_id` and `name`, and the outcome's `routine_id`, `status` and `run_id`. A goal's text and inputs stay out of the tool-use record.

## Tool guide

**TG-01.** Every tool carries a guide of three short texts: what it does, when to use it, and why it's useful. The catalog exposes them as `guide`, and a test fails for a tool without one.

**TG-02.** On the Tools page, choosing a tool opens a modal dialog instead of the side panel. It shows:
- the tool's title, availability and repair;
- What, When and Why;
- its inputs and outputs, with name, type, required and whether each is shown in records;
- Granted to, Copy schema and a link to the full detail page.

It keeps `?tool=<id>` in the URL. Escape, Close and a click outside close it, focus returns to the tool's link, and it passes axe in both themes.
