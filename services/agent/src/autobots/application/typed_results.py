"""browse_goal's typed result, Decision 0035 Y12 and Y19.

browser-use's output is untrusted data from the box. Every string in it that is an http(s) URL loses
its query and fragment, unless it sits in a link field the schema declares in `x-link-fields`, and
the result must then validate against the schema. A result that doesn't is refused, which stops the
call `invalid_action`.
"""

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]  # jsonschema ships no stubs
from jsonschema.exceptions import ValidationError  # type: ignore[import-untyped]  # jsonschema ships no stubs
from referencing.exceptions import Unresolvable


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
