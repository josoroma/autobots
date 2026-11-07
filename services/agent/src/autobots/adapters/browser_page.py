"""The browsing loop's page over the isolated executor's CDP session (Decision 0020 L1 and L2).

It reads a page as text, follows navigation and scrolls. It never types, clicks a button, submits
or evaluates anything the model wrote: the only script it runs is the fixed reader below. It is a
separate module from the executor so the executor's qualification fingerprint isn't touched.
"""

import asyncio
from typing import Any

from autobots.adapters.browser_executor import Cdp
from autobots.application.browsing_loop import MAX_LINKS, TEXT_CHARS, Link, PageView

# Fixed, and returns plain values only. Links are absolute https URLs, deduplicated, in order.
READER = f"""(() => {{
  const seen = new Set(); const links = [];
  for (const a of document.querySelectorAll('a[href]')) {{
    let url; try {{ url = new URL(a.href, location.href); }} catch (e) {{ continue; }}
    if (url.protocol !== 'https:') continue;
    url.hash = '';
    const href = url.toString();
    if (seen.has(href)) continue;
    seen.add(href);
    const text = (a.innerText || a.getAttribute('aria-label') || a.title || '').trim();
    links.push({{text: text.replace(/\\s+/g, ' ').slice(0, 200), url: href}});
    if (links.length >= {MAX_LINKS}) break;
  }}
  const body = document.body ? document.body.innerText : '';
  const above = Math.max(0, window.scrollY);
  return {{url: location.href, title: document.title || '', links,
           text: body.replace(/\\n{{3,}}/g, '\\n\\n').slice(0, {TEXT_CHARS * 4}), offset: above}};
}})()"""


class PageUnavailable(Exception):
    """The browser didn't answer or the page couldn't be read."""


class CdpPage:
    """One tab of the session. Scrolling moves the window of text the model is shown."""

    def __init__(self, cdp: Cdp, session: str, settle: float = 2.0) -> None:
        self._cdp = cdp
        self._session = session
        self._settle = settle
        self._scrolled = 0

    @classmethod
    async def open(cls, cdp: Cdp, settle: float = 2.0) -> "CdpPage":
        targets = (await cdp.send("Target.getTargets"))["result"]["targetInfos"]
        page = next((target for target in targets if target["type"] == "page"), None)
        if page is None:
            raise PageUnavailable("no page target")
        attached = await cdp.send(
            "Target.attachToTarget", {"targetId": page["targetId"], "flatten": True}
        )
        return cls(cdp, attached["result"]["sessionId"], settle)

    async def go(self, url: str) -> None:
        await self._cdp.send("Page.navigate", {"url": url}, self._session)
        self._scrolled = 0
        await asyncio.sleep(self._settle)

    async def scroll(self) -> None:
        self._scrolled += 1

    async def view(self) -> PageView:
        reply = await self._cdp.send(
            "Runtime.evaluate",
            {"expression": READER, "returnByValue": True, "awaitPromise": False},
            self._session,
        )
        value: Any = reply.get("result", {}).get("result", {}).get("value")
        if not isinstance(value, dict):
            raise PageUnavailable("the page could not be read")
        text = str(value.get("text", ""))
        start = min(self._scrolled * TEXT_CHARS, max(len(text) - TEXT_CHARS, 0))
        return PageView(
            url=str(value.get("url", "")),
            title=str(value.get("title", "")),
            text=text[start : start + TEXT_CHARS],
            links=tuple(
                Link(text=str(link.get("text", "")), url=str(link.get("url", "")))
                for link in value.get("links", [])[:MAX_LINKS]
                if isinstance(link, dict)
            ),
        )
