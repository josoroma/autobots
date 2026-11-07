## Why

US-14.7, [PRD-Tool-Catalog "Web tools"](../../../PRD-Tool-Catalog.md#web-tools) and Decision 0017 Q2: the requested "built-in" Search The Web and Extract Website Content are the Jina-backed tools AutoGPT ships under those names.

## What Changes

- `adapters/jina.py`: `search_web` (`s.jina.ai`, at most 10 results) and `extract_website_content` (`r.jina.ai` in reader mode, markdown with up to 100 links), read-only and metered, over plain `httpx` with an injectable transport, the key read per attempt.
- Reader requests always ask for markdown with no images and `X-With-Generated-Alt: false`, and never send a response engine such as ReaderLM. No input offers a model option, and `extract_website_content` takes only a URL, which passes the URL guard first.
- Output is labelled third-party, cut to the shared budget with a notice, and refusals are typed. The tools join the loop, the execution contract and the Expert-grantable set.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `web-tools`: Jina's two tools.

## Impact

`adapters/jina.py`, `contracts/web_tools.py`, `domain/tools.py`, `domain/execution.py`, `application/goal_loop.py`, `tests/test_jina.py` and `tests/db/web_tools_check.py`. No package added; no live Jina call made.
