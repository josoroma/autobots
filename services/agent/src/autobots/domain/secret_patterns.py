"""Secret shapes masked wherever text leaves the service: local logs and text shown to people.

XDUP-01: logs and shown text kept separate copies, and the shown copy fell behind the tool keys of
Decision 0017. Display redaction may only get stricter (SP-011), so both now mask every shape here.

Each shape is matched on the original text and the matches are merged, so a shape that starts
earlier can't hide where another one would have matched.
"""

import re
from collections.abc import Iterable

REDACTED = "[redacted]"
# How far a credential's value runs after its name, or a URL after its host.
_LOG_VALUE = r"\S+"
# Shown text also ends a value at a quote or where the next query parameter starts, so redacted
# JSON still parses and the rest of a request stays visible to the person reviewing it (PRUN-05).
_SHOWN_VALUE = r"""(?:[^\s"'&]|&(?![\w.-]+=))+"""


def _shapes(value: str) -> tuple[re.Pattern[str], ...]:
    return tuple(
        re.compile(source)
        for source in (
            # Model providers' keys, never inside a word, so "task-specific" stays readable.
            r"(?<![A-Za-z0-9])sk-or-[\w-]+",
            r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{4,}",
            # Tool providers' keys, Decision 0017: Tavily, Jina and GitHub tokens.
            r"tvly-[\w-]{8,}",
            r"jina_[A-Za-z0-9]{8,}",
            r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}",
            r"github_pat_[A-Za-z0-9_]{20,}",
            # A credential in a header, a token or a URL.
            r"(?i:bearer)\s+[\w.~+/=-]+",
            r"eyJ[\w-]+\.[\w-]+\.[\w-]*",
            r"eyJ[A-Za-z0-9_-]{10,}",
            r"\b(?:postgres(?:ql)?|https?)://[^\s/@]+:[^\s/@]+@" + value,
            r"\b(?:postgres(?:ql)?)://" + value,
            # A named credential, as text or a JSON field. Only its value is masked, after any
            # scheme, so "Authorization: Basic <value>" loses the value and keeps its name.
            r"(?i:password|passwd|token|secret|api[_-]?key|authorization)[\"']?\s*[=:]\s*[\"']?"
            r"(?i:(?:bearer|basic|token)\s+)?(?P<value>" + value + ")",
        )
    )


LOG_SHAPES = _shapes(_LOG_VALUE)
SHOWN_SHAPES = _shapes(_SHOWN_VALUE)


def mask(text: str, shapes: Iterable[re.Pattern[str]]) -> str:
    """Replaces every span any shape matches, merging overlapping and adjacent spans."""
    spans = sorted(
        match.span("value") if "value" in shape.groupindex else match.span()
        for shape in shapes
        for match in shape.finditer(text)
    )
    merged: list[list[int]] = []
    for start, end in spans:
        if start == end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    pieces: list[str] = []
    last = 0
    for start, end in merged:
        pieces += [text[last:start], REDACTED]
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def redact_shown(text: str) -> str:
    """For text shown to workspace members: plans, summaries, goals and approval arguments."""
    return mask(text, SHOWN_SHAPES)
