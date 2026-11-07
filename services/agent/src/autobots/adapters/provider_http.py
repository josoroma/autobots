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
