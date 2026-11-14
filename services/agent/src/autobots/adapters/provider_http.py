"""Tool-provider keys and HTTP, PRD-Tool-Catalog PK-01 to PK-03 and Decision 0017 Q1.

A key is resolved inside each attempt, for Tavily and Jina by PK-04's order (Decision 0024), and
handed to this attempt's HTTP client only. It never enters a scope, a tool's arguments or schema,
graph state, an event, a tool-use row, a receipt or a log line. Nothing here checks a key against
its provider: that would be a paid call, and only an owner's explicit task makes one. Tests pass a
fake transport.
"""

from collections.abc import Mapping

import httpx

from autobots.application.tool_gateway import ToolContext, ToolFailed
from autobots.domain.tool_catalog import KeyRequirement

DEFAULT_SECONDS = 20.0


async def attempt_key(
    context: ToolContext, requirement: KeyRequirement, environ: Mapping[str, str]
) -> str:
    """This attempt's key by PK-04's order, for the run's workspace. A failure names the credential,
    never the value, and the key goes to the caller's HTTP client only."""
    from autobots.application.tool_keys import ToolKeyMissing, ToolKeyUnavailable, resolve_tool_key

    try:
        return await resolve_tool_key(
            context.connection, context.scope.workspace_id, requirement, environ
        )
    except (ToolKeyMissing, ToolKeyUnavailable) as error:
        raise ToolFailed(error.code) from None


def provider_client(
    base_url: str,
    headers: Mapping[str, str],
    transport: httpx.AsyncBaseTransport | None = None,
    seconds: float = DEFAULT_SECONDS,
) -> httpx.AsyncClient:
    """One attempt's client. Redirects are never followed here: a tool that must follow one goes
    through the URL guard, which revalidates each target."""
    return httpx.AsyncClient(
        base_url=base_url,
        headers=dict(headers),
        transport=transport,
        timeout=seconds,
        follow_redirects=False,
        trust_env=False,
    )


def failure_for(credential: str, status: int) -> ToolFailed:
    """A provider's refusal as a typed code. Its body never reaches the model."""
    if status == 429:
        return ToolFailed("rate_limited")
    if status in (401, 403):
        return ToolFailed(f"{credential}_key_refused")
    if 400 <= status < 500:
        return ToolFailed(f"provider_refused_{status}")
    return ToolFailed("provider_unavailable")


# Characters of third-party text a web tool returns in all, shared among its results. The tool's
# byte cap stays well above it, so the cut, not the gateway, decides and the output says so.
TEXT_BUDGET = 100_000


def fit(texts: list[str], budget: int = TEXT_BUDGET) -> tuple[list[str], bool]:
    """Each text cut to an equal share of the budget, and whether any was cut."""
    if not texts:
        return [], False
    share = max(budget // len(texts), 1)
    cut = [text[:share] for text in texts]
    return cut, any(len(text) > share for text in texts)
