## Why

US-14.23, [Decision 0033](../../../docs/engineering/decisions/0033-google-toolkit-and-tool-switches.md) K1 to K9, and PRD-Tool-Catalog GT-01 and GT-02. The owner asked for Google to have its own map and crawl, like the other search providers. The rule is "find with Google, read with a Google equivalent", as one toolkit that can be turned off as a whole or tool by tool. The switches are US-14.24.

## What Changes

- A new tool group, Google (`google`). `google_search` moves into it; only its descriptor changes, and its version and schema stay.
- `google_map` v1 searches SerpApi for `site:<host><path>` and lists the pages Google has indexed, up to 30. It uses the shared pager, and drops results on other hosts.
- `google_extract` v1 reads up to 5 pages directly from their sites through the URL guard, as markdown:
  - it obeys robots.txt and fails closed, checking the final host after redirects;
  - it spaces requests to one host by 1 to 5 seconds, sends its own user agent and never retries;
  - it extracts with `trafilatura`.
- `google_crawl` v1 runs `google_map` for up to 10 pages, then reads them as `google_extract` does.
- A new provider, `direct`. `trafilatura` 2.3.1 is pinned, locked and named in the toolchain runbook.
- The seeded Google bot is granted the four Google tools, with save and publish.

## Capabilities

### New Capabilities

- `google-toolkit`: the Google group, `google_map`, `google_extract` and `google_crawl`, polite direct reading, extraction, metering and the pinned dependency.

### Modified Capabilities

- `google-search`: `google_search` belongs to the group `google`.
- `experts`: Google bot's grants are the toolkit.

## Impact

- **Backend:**
  - `adapters/google_reader.py` (new), `adapters/serpapi.py` and `adapters/tool_registry.py`;
  - `contracts/web_tools.py`, `contracts/tool_catalog.py`, `domain/tool_catalog.py`, `domain/tools.py`, `domain/execution.py` and `domain/tool_guides.py`;
  - `operations/concept_seed.py`.
- **Toolchain:** `services/agent/pyproject.toml`, `uv.lock` and `docs/engineering/runbooks/toolchains.md`.
- **Web:** the group and provider labels, and the regenerated client.
- **Tests:**
  - `test_google_reader.py` (new), `test_serpapi.py` and the pin, guide and seed tests;
  - the toolchain manifest test and the database checks.
- No migration and no live request.
