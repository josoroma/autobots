# Tasks

## 1. Dependency (The new dependency is pinned and recorded)

- [x] 1.1 Pin `trafilatura==2.3.1` in `services/agent/pyproject.toml`, run `scripts/toolchain.py lock` and `bootstrap`, and name it in the toolchain runbook's table. Checked by `tests/toolchain/test_manifests.py` and `uv sync --check --locked --offline`

## 2. Reader and tools (google_extract reads pages as markdown, politely; robots.txt is obeyed and fails closed; Page failures are typed and never retried; Extraction opens no connection of its own; google_map lists the pages; google_crawl maps a site, then reads its pages)

- [x] 2.1 Add `adapters/google_reader.py`, `google_extract`, `google_map` and `google_crawl` with their contracts. Checked by `services/agent/tests/test_google_reader.py` on fake resolvers and transports with a recorded sleep
- [x] 2.2 Add the group `google` and provider `direct`, move `google_search` into the group, register the three tools with guides, grants, version pins and digests, and add the web labels. Regenerate OpenAPI and the client. Checked by the pin, guide, catalog and web unit tests and `generate_contracts.py check`

## 3. Seed, record and docs (The Google group holds four tools; Google bot gets the toolkit; One metered call each)

- [x] 3.1 Give Google bot the toolkit in the seed and its checks. Checked by `test_concept_seed.py` and `concept_seed_check.py`
- [x] 3.2 Add a `google_extract` and `google_crawl` scenario to `tests/db/checks/web_tools_check.py`. Checked by the `db` profile
- [x] 3.3 Update `CODEBASE.md`
