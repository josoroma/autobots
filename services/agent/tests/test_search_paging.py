"""The search tools' pager, US-14.21 and Decision 0031 S2 to S7, driven with plain page lists."""

from collections.abc import Sequence

import pytest

from autobots.adapters.search_paging import (
    MAX_PAGES,
    PAGE_SIZE,
    Page,
    canonical_url,
    gather,
    pages_for,
)
from autobots.application.tool_definitions import ToolFailed


def page(start: int, count: int = PAGE_SIZE) -> list[tuple[str, str]]:
    return [(f"https://example.com/{n}", f"r{n}") for n in range(start, start + count)]


class Pages:
    """Serves the given pages in order and records each page number asked for. A page given as a
    ToolFailed raises it."""

    def __init__(self, *pages: list[tuple[str, str]] | ToolFailed) -> None:
        self.pages = pages
        self.asked: list[int] = []

    async def __call__(self, number: int) -> Sequence[tuple[str, str]]:
        self.asked.append(number)
        served = self.pages[number - 1] if number <= len(self.pages) else []
        if isinstance(served, ToolFailed):
            raise served
        return served


def test_a_call_plans_pages_of_ten_and_never_more_than_three() -> None:
    assert (PAGE_SIZE, MAX_PAGES) == (10, 3)
    targets = (1, 10, 11, 15, 20, 21, 30, 31, 100)
    assert [pages_for(n) for n in targets] == [1, 1, 2, 2, 2, 3, 3, 3, 3]


@pytest.mark.asyncio
async def test_three_full_pages_give_thirty_results_in_page_order() -> None:
    pages = Pages(page(0), page(10), page(20))
    found = await gather(pages, 30)
    assert pages.asked == [1, 2, 3]
    assert found.items == [f"r{n}" for n in range(30)]
    assert (found.pages, found.stopped, found.duplicates_removed, found.page_error) == (
        3,
        "enough",
        0,
        None,
    )


@pytest.mark.asyncio
async def test_a_smaller_target_asks_only_for_the_pages_it_needs() -> None:
    pages = Pages(page(0), page(10), page(20))
    found = await gather(pages, 15)
    assert pages.asked == [1, 2]
    assert found.items == [f"r{n}" for n in range(15)]
    assert (found.pages, found.stopped) == (2, "enough")


@pytest.mark.asyncio
async def test_a_short_page_stops_the_paging() -> None:
    pages = Pages(page(0), page(10, count=4), page(20))
    found = await gather(pages, 30)
    assert pages.asked == [1, 2]
    assert len(found.items) == 14
    assert (found.pages, found.stopped) == (2, "no_more")


@pytest.mark.asyncio
async def test_a_page_that_adds_nothing_new_stops_the_paging() -> None:
    pages = Pages(page(0), page(0), page(0))
    found = await gather(pages, 30)
    assert pages.asked == [1, 2]
    assert len(found.items) == 10
    assert (found.pages, found.stopped, found.duplicates_removed) == (2, "no_more", 10)


@pytest.mark.asyncio
async def test_the_planned_pages_spent_while_short_is_page_limit() -> None:
    # Page 2 repeats half of page 1, so two pages hold 15 distinct results for a target of 20.
    pages = Pages(page(0), page(0, count=5) + page(10, count=5), page(20))
    found = await gather(pages, 20)
    assert pages.asked == [1, 2]
    assert len(found.items) == 15
    assert (found.pages, found.stopped, found.duplicates_removed) == (2, "page_limit", 5)


@pytest.mark.asyncio
async def test_duplicates_are_dropped_by_canonical_url_keeping_the_first_as_given() -> None:
    first = page(0)
    repeats = [
        ("https://example.com/0?utm_source=x&utm_medium=y", "again0"),
        ("https://example.com/1#section", "again1"),
        ("https://EXAMPLE.com/2", "again2"),
        ("https://example.com/3/", "again3"),
        ("https://example.com/4?gclid=abc", "again4"),
    ]
    pages = Pages(first, repeats + page(10, count=5), page(20))
    found = await gather(pages, 20)
    assert found.items[:10] == [f"r{n}" for n in range(10)]
    assert found.items[10:] == [f"r{n}" for n in range(10, 15)]
    assert found.duplicates_removed == 5
    assert not any(item.startswith("again") for item in found.items)


def test_canonical_url_keeps_what_distinguishes_a_page() -> None:
    assert canonical_url("https://Example.COM/a/?utm_x=1&id=7#top") == "https://example.com/a?id=7"
    assert canonical_url("https://example.com/a?id=7") != canonical_url(
        "https://example.com/a?id=8"
    )
    assert canonical_url("https://example.com/a") != canonical_url("https://example.com/b")
    assert canonical_url("http://[::1") == "http://[::1"


@pytest.mark.asyncio
async def test_results_without_a_url_are_never_counted_as_repeats() -> None:
    pages = Pages([("", "a"), ("", "b"), ("https://example.com/x", "c")])
    found = await gather(pages, 10)
    assert found.items == ["a", "b", "c"]
    assert (found.duplicates_removed, found.stopped) == (0, "no_more")


@pytest.mark.asyncio
async def test_a_later_page_failure_keeps_the_earlier_pages_and_its_code() -> None:
    pages = Pages(page(0), ToolFailed("rate_limited"), page(20))
    found = await gather(pages, 30)
    assert pages.asked == [1, 2]
    assert found.items == [f"r{n}" for n in range(10)]
    assert (found.pages, found.stopped, found.page_error) == (2, "provider_error", "rate_limited")


@pytest.mark.asyncio
async def test_a_first_page_failure_is_the_calls_failure() -> None:
    pages = Pages(ToolFailed("provider_unavailable"), page(10))
    with pytest.raises(ToolFailed) as failed:
        await gather(pages, 30)
    assert str(failed.value) == "provider_unavailable"
    assert pages.asked == [1]


@pytest.mark.asyncio
async def test_a_page_longer_than_its_size_is_cut_and_a_target_is_never_exceeded() -> None:
    pages = Pages(page(0, count=12))
    found = await gather(pages, 5)
    assert found.items == [f"r{n}" for n in range(5)]
    assert (found.pages, found.stopped) == (1, "enough")


@pytest.mark.asyncio
async def test_one_request_for_the_whole_target_when_a_provider_cant_page() -> None:
    """Tavily's shape (S3): one page as large as the target, planned once."""
    pages = Pages(page(0, count=20))
    found = await gather(pages, 20, page_size=20, planned=1)
    assert pages.asked == [1]
    assert (len(found.items), found.pages, found.stopped) == (20, 1, "enough")
    short = Pages(page(0, count=7))
    found = await gather(short, 20, page_size=20, planned=1)
    assert (len(found.items), found.stopped) == (7, "no_more")


class Signalled:
    """Pages that say whether another exists, as SerpApi's do (Decision 0032 G3)."""

    def __init__(self, *pages: Page[str]) -> None:
        self.pages = pages
        self.asked: list[int] = []

    async def __call__(self, number: int) -> Page[str]:
        self.asked.append(number)
        return self.pages[number - 1]


@pytest.mark.asyncio
async def test_a_short_page_that_says_more_exist_keeps_the_paging() -> None:
    pages = Signalled(Page(page(0, count=8), more=True), Page(page(10), more=False), Page(page(20)))
    found = await gather(pages, 30)
    assert pages.asked == [1, 2]
    assert len(found.items) == 18
    assert (found.pages, found.stopped) == (2, "no_more")


@pytest.mark.asyncio
async def test_a_full_page_that_says_none_remain_stops_the_paging() -> None:
    pages = Signalled(Page(page(0), more=False), Page(page(10), more=True))
    found = await gather(pages, 30)
    assert pages.asked == [1]
    assert (len(found.items), found.stopped) == (10, "no_more")


@pytest.mark.asyncio
async def test_an_empty_page_that_says_none_remain_is_no_more_not_an_error() -> None:
    pages = Signalled(Page(page(0), more=True), Page([], more=False))
    found = await gather(pages, 30)
    assert (len(found.items), found.pages, found.stopped, found.page_error) == (
        10,
        2,
        "no_more",
        None,
    )
