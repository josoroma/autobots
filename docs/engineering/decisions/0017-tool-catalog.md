# Decision 0017: Tool catalog, tool-use record and tool providers

**Date:** 2026-11-07. **Authority:** the owner, who asked the session to implement [the tool-catalog plan](../../plan/tool-catalog.md), to take the best-reasoned decision on every point the plan left open, to approve those decisions and to continue. That approves [PRD-Tool-Catalog.md](../../PRD/PRD-Tool-Catalog.md) and schedules [EPIC-14](../../../SPECS.md#epic-14-tool-catalog-and-tool-use-record). Each answer below is the option the session reasoned best. The owner can change any of them under the story ID it affects.

## Decision

### Conflicts with existing rules

| # | Choice |
|---|---|
| **C1. Tool providers** | Tavily, Jina, Yahoo Finance's chart endpoint and the World Bank Indicators API are **tool providers**: data services the local worker calls as tools, as PRD §2.3 allows. They are not inference providers. OpenRouter stays the only inference provider. GitHub stays a connector under Decision 0007 |
| **C2. Inference inside a tool provider** | Forbidden. No tool schema offers an option that makes the provider run a model (Tavily `include_answer`, `auto_parameters`, natural-language crawl `instructions`; Jina's model-based reader options), and each adapter sends such options off or absent. Opening one needs its own decision |
| **C3, C4. browser-use** | Not adopted in this epic. Its descriptor is shown as `disabled_by_policy`, and it is never registered. US-14.12 stays `BLOCKED` on an isolated executor and an admitted-model adapter, both unwritten |
| **C5. Paid calls** | No live provider call is authorized. Every test uses a fake transport, even with a real key present. Stories are `DONE` on fakes because their scenarios say so; that never establishes a provider works live. Live qualification of a provider is a separate, owner-capped task |
| **C6. URL guard** | One shared guard for every URL a tool fetches or sends to a provider: `https` only, no credentials in the URL, DNS answers checked against loopback, private, link-local, multicast, reserved and metadata ranges, every redirect revalidated, size and time caps. Required before any tool fetches a URL itself |
| **C7. Code tools** | Over the run's virtual files only, with names that never match the SDK's file tools: `search_files`, `read_code_file`, `write_code_file`, `patch_code_file`. Search is pure Python, with no `rg` binary |
| **C8. GitHub variable names** | The owner's commit `ec8b31a` renamed them to `GITHUB_REPOSITORY` and `GITHUB_TOKEN`. That stands as the owner's choice. Decision 0007's credential rule, a token limited to that repository's issues, is unchanged, and the operations runbook warns that a broader developer token under that name would be picked up |
| **C9. Tools screen** | PRD-Tool-Catalog.md adds it to PRD §12.1's required screens, placed in the sidebar before Settings |
| **C10. Inputs and outputs on screens** | Only fields a tool's definition lists as public, plus digests and sizes. The default is none |
| **C11. Yahoo terms** | Accepted for a single-owner local install. Outputs name the source, say it is unofficial and carry timestamps |
| **C12. Dependencies** | No new package. Every provider adapter is plain `httpx`, which is already pinned. `yfinance` is not added: the tool calls the same chart endpoint yfinance uses, which avoids `pandas` and keeps one fake-transport pattern |

### Open questions

| # | Choice |
|---|---|
| **Q1. Key storage** | Worker environment only, read per attempt, as Decision 0007. No app-managed sealed tool keys or Settings form in this epic |
| **Q2. "Built-in" tools** | Search The Web and Extract Website Content are the Jina-backed tools AutoGPT ships under those names: `s.jina.ai` and `r.jina.ai` in reader mode |
| **Q3. Why, and public fields** | "Why" is the plan task the call served, by `task_id`, shown with the task's title from the run's plan. No model-written purpose is stored. Search queries and URLs, with query strings and fragments removed, are public for the tools that take them. Page text, CSV rows and file content are never public: only their digest and size |
| **Q4. Tool spend** | No money ledger for tools. Each tool use records the provider units a provider reports. A root run tree may make at most **20 metered tool calls** (`metered_tool_calls`); the next is denied with `tool_budget_exceeded` before any request |
| **Q5. Inflation** | The World Bank Indicators API, indicator `FP.CPI.TOTL.ZG` (consumer prices, annual %), for Costa Rica (`CRI`), the USA (`USA`) and the euro area (`EMU`). No key. Annual only. yfinance is not an inflation source |
| **Q6. EUR to CRC** | The market tool accepts any Yahoo symbol matching its pattern, including `EURCRC=X`. If Yahoo doesn't serve it, the tool returns `symbol_not_found` and a run can use `EURUSD=X` with `CRC=X`. The tool computes no crosses |
| **Q7. Yahoo terms** | As C11 |
| **Q8. Code tools** | Run files only. `patch_code_file` takes exact string replacement (`old_string`, `new_string`, `replace_all`), not unified diffs |
| **Q9. browser-use** | As C3 and C4 |
| **Q10. Agent File Input** | Not a catalog tool, since no model calls it. It is a run-input feature: the goal composer attaches text files to a run's `inputs/`. Registry–catalog parity stays exact |
| **Q11. File types and caps** | Text types only: plain text, markdown, JSON and CSV. No PDF, DOCX or XLSX. 1 MiB per attached or stored file, 5 attached files per run. `read_run_file` version 2 adds the media type and line paging |
| **Q12. GitHub variable names** | As C8 |
| **Q13. Event compatibility** | New event types keep `schema_version: 1`. The generated client and the event consumer learn them in the same change that first emits them, and the consumer ignores a type it doesn't know |
| **Q14. Scope and order** | EPIC-14 is scheduled now, independent of EPIC-13. Catalog, record and readiness come first, then the URL guard, then providers one at a time |

## Requirements revised

- PRD §12.1 gains the Tools screen, through PRD-Tool-Catalog.md.
- PRD §11.3 gains the `tool.use.started` and `tool.use.completed` event types.
- Nothing else in the Option B contract changes. Arbitrary execution stays disabled.

## What this gives up

- **No browser automation**, and no code tools over a real repository, until an isolated executor exists.
- **Inflation is annual**, and the World Bank publishes with a lag.
- **No monetary cap on tool spend**, only a call count. A deep crawl inside the count can still use many credits; schema ceilings bound it.
- **Environment keys only.** Changing a tool key means restarting the worker.
- **Unofficial market data** can break without notice.

## What this doesn't establish

That any provider tool works against its live service. Fake transports and recorded fixtures prove the adapters' contracts and refusals, not the provider's current behavior. Neither H1 nor product acceptance follows from this epic.

## Reversal

Each tool can be removed from the registry. Saved runs that pinned its version would stop as `incompatible_version`, with a linked new run as the way forward. Tool-use rows stay under workspace retention.

## Amended

[Decision 0022](0022-studio-product-surfaces.md) D2 moves Tools under **Build**, after Workflows, in place of C9's position directly before Settings.

[Decision 0036](0036-inflation-rates-removed.md) R1 removes `inflation_rates` and the World Bank Indicators API, so C1's providers are Tavily, Jina and Yahoo Finance's chart endpoint, and Q5 no longer holds. By its R5, a tool it retires doesn't stop a saved run, so the Reversal's `incompatible_version` holds for a tool removed without being retired.
