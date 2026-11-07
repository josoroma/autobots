"""Tool-provider keys and HTTP, PRD-Tool-Catalog PK-01 to PK-03 and Decision 0017 Q1.

A key is read from the worker's environment inside each attempt and handed to this attempt's HTTP
client only. It never enters a scope, a tool's arguments or schema, graph state, an event, a
tool-use row, a receipt or a log line. Nothing here checks a key against its provider: that would be
a paid call, and only an owner's explicit task makes one. Tests pass a fake transport.
"""

from collections.abc import Mapping

import httpx

from autobots.application.tool_gateway import ToolFailed
from autobots.domain.tool_catalog import KeyRequirement

DEFAULT_SECONDS = 20.0


def provider_key(requirement: KeyRequirement, environ: Mapping[str, str]) -> dict[str, str]:
    """This attempt's values, or a typed failure naming the credential, never the value."""
    values = {name: environ.get(name, "").strip() for name in requirement.variables}
    if not all(values.values()):
        raise ToolFailed(f"{requirement.credential}_key_missing")
    return values


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
