"""browse_goal's typed result, Decision 0035 Y12 and Y19, and the file it is saved as, Decision
0039.

browser-use's output is untrusted data from the box. Every string in it that is an http(s) URL loses
its query and fragment, unless it sits in a link field the schema declares in `x-link-fields`, and
the result must then validate against the schema. A result that doesn't is refused, which stops the
call `invalid_action`. A layout writes each of its items as one line, in order and as it came.
"""

import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]  # jsonschema ships no stubs
from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]  # jsonschema ships no stubs
from referencing.exceptions import Unresolvable

from autobots.contracts.browsing import PLACEHOLDER, SaveResult


class ResultRefused(ValueError):
    """The result doesn't validate against the call's output schema."""


def _bare(text: str) -> str:
    parts = urlsplit(text)
    if parts.scheme in ("http", "https") and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return text


def _cleaned(value: Any, links: frozenset[str], path: str = "") -> Any:  # noqa: ANN401 - untrusted JSON
    if isinstance(value, Mapping):
        return {
            key: _cleaned(item, links, f"{path}.{key}" if path else str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_cleaned(item, links, f"{path}[]") for item in value]
    if isinstance(value, str) and path not in links:
        return _bare(value)
    return value


def typed_result(output: Any, schema: Mapping[str, Any]) -> Any:  # noqa: ANN401 - untrusted JSON
    """The result with bare URLs outside its link fields, valid against `schema`, or refused."""
    links = schema.get("x-link-fields", [])
    cleaned = _cleaned(output, frozenset(link for link in links if isinstance(link, str)))
    try:
        Draft202012Validator(dict(schema)).validate(cleaned)
    except (ValidationError, Unresolvable) as error:
        raise ResultRefused("the result doesn't match the output schema") from error
    return cleaned


def _text(value: Any) -> str:  # noqa: ANN401 - untrusted JSON
    """One value on one line: its text, trimmed, with one space for a line break, else its JSON."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return " ".join(part for part in map(str.strip, value.splitlines()) if part)


def _storable(text: str) -> str:
    """Page text can hold a NUL or half a surrogate pair, which a text column or UTF-8 refuses."""
    return text.replace("\x00", "").encode("utf-8", "replace").decode()


def _filled(text: str, values: Mapping[str, Any]) -> str:
    return PLACEHOLDER.sub(lambda name: _text(values.get(name[1])), text)


def items_of(result: Any, save: SaveResult) -> list[Any] | None:  # noqa: ANN401 - a validated result
    """The layout's items, or None when it names none. A schema may leave the property out, which
    holds no items."""
    if save.items is None:
        return None
    found = result.get(save.items) if isinstance(result, Mapping) else None
    return found if isinstance(found, list) else []


def rendered(result: Any, save: SaveResult) -> str:  # noqa: ANN401 - a validated result
    """The file's text (Decision 0039 V2 and V3): the text before the items, a blank line, then one
    line per item, or the result as indented JSON when there is no layout."""
    items = items_of(result, save)
    if items is None:
        return _storable(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    lines = [_filled(save.line, item if isinstance(item, Mapping) else {}) for item in items]
    before = _filled(save.before, result if isinstance(result, Mapping) else {}).rstrip("\n")
    return _storable("\n".join([before, "", *lines] if before else lines) + "\n")
