---
name: autobots-python
description: Implement or review typed Python domain, application and FastAPI code in services/agent, with offline contract generation, async lifecycle ownership and controlled tests.
---

# Python application boundaries

Read `.claude/autobots.json`, the mapped contract, selected story and [Python standards in DH-06](../../../PRD-Development-Harness.md#python-api-domain-and-workers). Use `autobots-durable-worker` for graph/job ownership changes and `autobots-contracts` for public schema changes.

- Keep domain/application logic separate from FastAPI, SQL and provider adapters. Pydantic owns external DTOs; persistence rows, graph state and public contracts are distinct types.
- Use the qualified Python 3.12 `src` package and prepared locked environment. Explicit installation may use `uv sync --locked`; checks must not silently sync or install dependencies.
- Build a pure FastAPI app factory so OpenAPI generation requires no database, model key or network call. Own pools/HTTP clients in lifespan and close them on shutdown.
- Use timezone-aware UTC, validated IDs, explicit enums/unions and exact integer/decimal money. Bound timeouts/retries/concurrency; keep blocking work off the event loop and propagate cancellation after cleanup.
- Test behavior with injected clocks/transports. Once implemented, run Ruff lint and formatting separately, strict mypy for owned modules and focused pytest coverage; document narrow third-party typing exceptions.

Return changed behavior/interfaces, lifecycle and cancellation implications, actual verification and unresolved gaps. Do not start services or call a provider to make an import test pass. Keep the DH-W work record current.
