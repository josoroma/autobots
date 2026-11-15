"""Tool-provider keys and HTTP, PRD-Tool-Catalog PK-01 to PK-03 and Decision 0017 Q1.

A key is resolved inside each attempt, for Tavily and Jina by PK-04's order (Decision 0024), and
handed to this attempt's HTTP client only. It never enters a scope, a tool's arguments or schema,
graph state, an event, a tool-use row, a receipt or a log line. Nothing here checks a key against
its provider: that would be a paid call, and only an owner's explicit task makes one. Tests pass a
fake transport.

`http_client` makes every tool connector's client, the URL guard's, Storage's and the OpenRouter
metadata client's (refactor plan R-62, PADP-05). Three clients are made elsewhere, each for its own
reason: the browser executor's, for the local DevTools endpoint, is part of the browser image
fingerprint; and the live-key check's usage client and the paid trials' client in
operations/reasoning_trial.py are operator tasks against OpenRouter, like the inference SDK's own
client, outside the tool path.

Every tool request maps its reply here: a read's failure is a typed code, and a write's is a failure
only when the reply proves nothing was written; anything else stays unknown for a readback to settle
(tool_gateway.ToolFailed).
"""

from collections.abc import Callable, Mapping
from typing import Annotated, Literal

import httpx
from pydantic import BaseModel, BeforeValidator, ConfigDict

from autobots.application.tool_gateway import OutcomeUnknown, ToolContext, ToolFailed
from autobots.domain.tool_catalog import KeyRequirement

MALFORMED = "provider_reply_malformed"


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


def http_client(
    base_url: str = "",
    *,
    timeout: float | httpx.Timeout,
    headers: Mapping[str, str] | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """The one way a client is made (PADP-05). A redirect is never followed: a tool that must follow
    one goes through the URL guard, which revalidates each target. The process environment's proxy,
    certificate and netrc settings are never read, so a key can't be routed elsewhere by them."""
    return httpx.AsyncClient(
        base_url=base_url,
        headers=dict(headers or {}),
        transport=transport,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )


class ProviderReply(BaseModel):
    """A provider reply's shape, adapter-private: only the fields a tool uses, and anything else the
    provider sends is ignored (PADP-07). These are never public contracts."""

    model_config = ConfigDict(extra="ignore")


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None


def _objects(value: object) -> object:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else value


def _strings(value: object) -> object:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else value


# A string field. Null reads as empty, never as the text "None".
Text = Annotated[str, BeforeValidator(_text)]
# A number field. Anything that isn't a number reads as unknown.
Number = Annotated[float | None, BeforeValidator(_number)]
# Lists whose items that aren't objects, or aren't strings, a provider sent are skipped.
Objects = BeforeValidator(_objects)
Strings = BeforeValidator(_strings)


class UnclearReply(OutcomeUnknown):
    """A reply doesn't say whether a write happened, so it stays unknown until a readback settles
    it. The receipt keeps `<provider>_unclear_<status>` as its category, and
    `<provider>_unclear_unreachable` when no reply came at all (R-25, XERR-02)."""

    def __init__(self, provider: str, status_code: int | None) -> None:
        reason = "unreachable" if status_code is None else str(status_code)
        super().__init__(f"{provider}_unclear_{reason}")
        self.status_code = status_code


def refusal_code(credential: str, status: int) -> str:
    """A provider's refusal as a typed code. Its body never reaches the model."""
    if status == 429:
        return "rate_limited"
    if status in (401, 403):
        return f"{credential}_key_refused"
    if 400 <= status < 500:
        return f"provider_refused_{status}"
    return "provider_unavailable"


def parsed[T: BaseModel](reply: httpx.Response, model: type[T]) -> T:
    """A read's reply in the shape the tool uses, or `provider_reply_malformed`."""
    try:
        return model.model_validate_json(reply.content)
    except ValueError:  # pydantic's ValidationError is a ValueError
        raise ToolFailed(MALFORMED) from None


async def read(
    client: httpx.AsyncClient,
    method: Literal["GET", "POST"],
    path: str,
    *,
    code_for: Callable[[int], str],
    unreachable: str = "provider_unavailable",
    params: Mapping[str, str | int] | None = None,
    json: object = None,
) -> httpx.Response:
    """A read that answered 200. Nothing is written, so any other outcome is a typed failure."""
    try:
        reply = await client.request(method, path, params=params, json=json)
    except httpx.HTTPError:
        raise ToolFailed(unreachable) from None
    if reply.status_code != 200:
        raise ToolFailed(code_for(reply.status_code))
    return reply


async def read_json[T: BaseModel](
    client: httpx.AsyncClient,
    method: Literal["GET", "POST"],
    path: str,
    model: type[T],
    *,
    code_for: Callable[[int], str],
    unreachable: str = "provider_unavailable",
    params: Mapping[str, str | int] | None = None,
    json: object = None,
) -> T:
    reply = await read(
        client,
        method,
        path,
        code_for=code_for,
        unreachable=unreachable,
        params=params,
        json=json,
    )
    return parsed(reply, model)


async def write(
    client: httpx.AsyncClient,
    path: str,
    payload: Mapping[str, object],
    *,
    provider: str,
    refused: frozenset[int],
    unreachable: str = "destination_unreachable",
) -> httpx.Response:
    """A create that answered 201. Only a connection that never opened, or a status in `refused`,
    proves nothing was written. Any other status is an `UnclearReply`, and any other transport
    error propagates, so both stay unknown and are never sent again unread."""
    try:
        reply = await client.post(path, json=payload)
    except (httpx.ConnectError, httpx.ConnectTimeout):
        raise ToolFailed(unreachable) from None
    if reply.status_code in refused:
        raise ToolFailed(f"{provider}_refused_{reply.status_code}")
    if reply.status_code != 201:
        raise UnclearReply(provider, reply.status_code)
    return reply


async def write_json[T: BaseModel](
    client: httpx.AsyncClient,
    path: str,
    payload: Mapping[str, object],
    model: type[T],
    *,
    provider: str,
    refused: frozenset[int],
) -> T:
    """A create's reply in the shape the tool uses. One that can't be read after a 201 may still
    have been written, so it stays unknown."""
    reply = await write(client, path, payload, provider=provider, refused=refused)
    try:
        return model.model_validate_json(reply.content)
    except ValueError:
        raise UnclearReply(provider, reply.status_code) from None


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
