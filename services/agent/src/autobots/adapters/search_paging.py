"""Search results in pages of 10, at most 3 a call, Decision 0031 S2 to S7 and PRD-Tool-Catalog
WS-02 to WS-06.

A search tool hands `gather` a fetch for one page and the call's target. The pager plans the pages,
drops repeats by canonical URL, keeps the first occurrence as the provider gave it, and stops at the
first of:
- the call has its target (`enough`);
- a page is short or adds nothing new (`no_more`);
- the planned pages are spent (`page_limit`);
- a later page fails (`provider_error`), its typed code kept as `page_error`.

A first page's failure is the call's failure. No page is retried, since each one spends the
provider's credits (S6).
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from math import ceil
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from autobots.application.tool_definitions import ToolFailed
from autobots.contracts.web_tools import SearchStop

PAGE_SIZE = 10
MAX_PAGES = 3
# What a paged search's tool uses show, beside its public inputs (Decision 0031 S8).
PUBLIC_OUTPUT = (
    "result_count",
    "pages",
    "stopped",
    "duplicates_removed",
    "page_error",
    "truncated",
)
# Click identifiers that name the same page under another address (Decision 0031 S4).
CLICK_IDS = frozenset({"gclid", "fbclid", "msclkid", "mc_cid", "mc_eid"})


def canonical_url(url: str) -> str:
    """The identity two results share when they are the same page: scheme and host lowercased,
    without the fragment, `utm_*` or click identifiers, or a trailing slash. Only compared, never
    shown: a result keeps the URL its provider gave."""
    text = url.strip()
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    query = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if not name.lower().startswith("utm_") and name.lower() not in CLICK_IDS
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), "")
    )


def pages_for(max_results: int) -> int:
    """The pages a call plans for its target, never more than `MAX_PAGES` (S2)."""
    return min(ceil(max_results / PAGE_SIZE), MAX_PAGES)


@dataclass(frozen=True)
class Gathered[T]:
    """A call's results in rank order, and how its paging went."""

    items: list[T]
    pages: int
    stopped: SearchStop
    duplicates_removed: int
    page_error: str | None = None


async def gather[T](
    # One page's results, each with the URL it is de-duplicated by. An empty URL never repeats.
    fetch: Callable[[int], Awaitable[Sequence[tuple[str, T]]]],
    max_results: int,
    *,
    page_size: int = PAGE_SIZE,
    planned: int | None = None,
) -> Gathered[T]:
    """Pages 1 to `planned`, by default `pages_for(max_results)`, in order, until a stop rule
    holds. A page longer than `page_size` is cut to it, and one shorter means the provider has no
    more."""
    plan = pages_for(max_results) if planned is None else min(planned, MAX_PAGES)
    kept: list[T] = []
    seen: set[str] = set()
    removed = 0
    for page in range(1, plan + 1):
        try:
            found = list(await fetch(page))
        except ToolFailed as error:
            if page == 1:
                raise
            return Gathered(kept, page, "provider_error", removed, str(error) or "tool_failed")
        added = 0
        for url, item in found[:page_size]:
            if len(kept) >= max_results:
                break
            identity = canonical_url(url) if url.strip() else None
            if identity is not None:
                if identity in seen:
                    removed += 1
                    continue
                seen.add(identity)
            kept.append(item)
            added += 1
        if len(kept) >= max_results:
            return Gathered(kept, page, "enough", removed)
        if len(found) < page_size or added == 0:
            return Gathered(kept, page, "no_more", removed)
    return Gathered(kept, plan, "page_limit", removed)
