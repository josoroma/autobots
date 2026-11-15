"""HTTP for the qualifiers, against the disposable stacks they start (SCRP-14).

Moved from qualify_identity.py, which seven scripts imported for it (SCRP-06).
"""
from __future__ import annotations

from collections.abc import Mapping
from urllib import error, request


def http(method: str, url: str, headers: Mapping[str, str] | None = None, body: bytes | None = None) -> tuple[int, str]:
    """The status and body of one request. An HTTP error's status and body are returned like any other reply."""
    try:
        with request.urlopen(request.Request(url, data=body, method=method, headers=dict(headers or {})), timeout=20) as reply:
            return int(reply.status), bytes(reply.read()).decode(errors='replace')
    except error.HTTPError as failure:
        return int(failure.code), bytes(failure.read()).decode(errors='replace')
