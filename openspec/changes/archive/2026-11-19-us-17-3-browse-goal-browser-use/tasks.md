# Tasks

## 1. Environment and image (Qualified again for browser-use; Nothing reaches Browser Use's cloud)

- [x] 1.1 `services/browser-use/` with `pyproject.toml`, `uv.lock` (browser-use 1.0.6, apart from the worker's lock), `runner.py` and an ignore for its local environment, and the resolved dependency tree recorded below. Checked by a harness test under `tests/harness` that reads the lock's pin and the project's dependency
- [x] 1.2 `infra/browser/browser-use.Dockerfile` and its ignore file, from the digest-pinned Playwright image with uv by digest, `uv sync --frozen`, telemetry and the update check off, `pwuser`. The browser image gains the managed policy `DownloadRestrictions` 3. Checked by building with `make browser-images` and by the qualification's cases
- [x] 1.3 `browser_qualification.py`: the browser-use image, its fingerprint, required cases, report and `browser_use_qualified`. `scripts/browser_images.py` builds and checks three images, each with its own digest. Checked by pytest under `services/agent/tests` with fake reports and labels: a missing case, a stale fingerprint, a stale label or an unqualified executor reads not qualified

## 2. Executor and engine (YOLO chooses the engine; Longer limits for browser-use only; A refused model request ends the browse; The domains and the box hold)

- [x] 2.1 `BrowserExecutor.run_browser_use`: one container per call on the session's internal network only, with BX-01's hardening and caps, its spec in one variable, removed with the session. The guard logs top-frame navigations and downloads. Checked by pytest under `services/agent/tests` on the Docker arguments and by the qualification
- [x] 2.2 `adapters/browser_use_box.py`: the endpoint guard (refused navigations, downloads and browser-use's own refusals refuse the next request `refused_action` before admission; admission refusals recorded; past `max_steps` + 1 calls refused) and the outcome mapping. Checked by pytest under `services/agent/tests` with a fake admission and a fake CDP log
- [x] 2.3 `browse_goal` version 2 with optional limits up to 40 and 600, version 1 unchanged, the engine per call (Y15) and the limits per engine (Y9). Move `EXPERT_TOOLS` and the schema fixture to version 2. Checked by pytest under `services/agent/tests` with a scripted model and fake executor, and `test_tool_schema_versions.py`

## 3. Live checks (every scenario)

- [x] 3.1 `tests/db/checks/browser_use_check.py`, run by `scripts/qualify_browser_executor.py` into its own report, through the real gateway, admission and endpoint on a disposable stack with a scripted model, reaching only https://example.com/. It covers each of the following:
  - a YOLO call that runs on browser-use with no approval, and after YOLO is off, one that waits and runs on the loop;
  - the same output contract;
  - one admitted call per request;
  - an outside navigation, a proxy-refused navigation and a download, each `refused_action`;
  - a page's refused subresource counted while the browse continues;
  - no Browser Use host in the proxy log;
  - the limits and box cap;
  - budget and cancel refusals ending the browse with their code;
  - the container's inspection.
- [x] 3.2 Rebuild the images and run the qualification. The executor and browser-use both pass

## 4. Documents

- [x] 4.1 Amend PRD-Tool-Catalog BX-01 for the 600-second browser-use cap and the image. Update `README-DEV.md`, the operations runbook's browser executor section and `CODEBASE.md`. Checked by reading them against Decision 0035 Y5 to Y9

## Resolved dependency tree

From `services/browser-use/uv.lock`: 62 packages for Python 3.12, locked apart from the worker's lock. They are installed only in the box's image, which reaches nothing but its proxy and its browser.

- **browser-use 1.0.6 requires:** browser-harness 0.1.13, genai-prices 0.2.1, google-genai 2.34.0, idna 3.20, mcp 2.3.0, pillow 12.3.0, pydantic 2.14.3, pydantic-ai-slim 2.66.0, python-dotenv 1.2.4, uuid7 0.1.0.
- **All resolved:** annotated-types 0.8.0, anthropic 2.11.0, anyio 4.16.0, attrs 26.1.0, browser-harness 0.1.13, browser-use 1.0.6, cdp-use 1.4.5, certifi 2026.10.23, cffi 2.1.1, charset-normalizer 3.5.2, click 8.5.1, cryptography 50.0.2, distro 1.9.0, docstring-parser 0.18.0, fetch-use 0.4.0, genai-prices 0.2.1, google-auth 2.62.2, google-genai 2.34.0, griffelib 2.4.1, h11 0.16.0, httpcore 1.0.9, httpcore2 2.16.2, httpx 0.28.1, httpx2 2.16.2, httpx2-jsfetch 1.0, idna 3.20, jiter 0.19.0, jsonschema 4.26.0, jsonschema-specifications 2025.9.1, logfire-api 6.0.0, mcp 2.3.0, mcp-types 2.3.0, openai 3.56.0, opentelemetry-api 1.45.2, pillow 12.3.0, pyasn1 0.6.5, pyasn1-modules 0.4.2, pycparser 3.12, pydantic 2.14.3, pydantic-ai-slim 2.66.0, pydantic-core 2.50.4, pydantic-graph 2.66.0, pyjwt 2.15.1, python-dotenv 1.2.4, python-multipart 0.0.34, pywin32 312, referencing 0.37.0, regex 2026.11.19, requests 2.34.2, rpds-py 2026.9.1, sniffio 1.3.1, sse-starlette 3.7.0, starlette 1.10.0, tenacity 9.1.4, tiktoken 0.14.0, truststore 0.10.5, typing-extensions 4.16.0, typing-inspection 0.4.5, urllib3 2.8.0, uuid7 0.1.0, uvicorn 0.54.0, websockets 15.0.1.
