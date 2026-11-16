"""PRD-Studio SR-01: what a person types is matched anywhere in a name or goal, literally, with
plain values (PPRD-16). ILIKE's wildcards and its escape character match only themselves."""

import pytest

from autobots.application.search import _pattern


@pytest.mark.parametrize(
    ("typed", "pattern"),
    [
        ("brief", "%brief%"),
        ("50%", "%50\\%%"),
        ("a_b", "%a\\_b%"),
        ("C:\\temp", "%C:\\\\temp%"),
        ("\\%_", "%\\\\\\%\\_%"),
        ("", "%%"),
    ],
)
def test_typed_text_matches_anywhere_and_literally(typed: str, pattern: str) -> None:
    assert _pattern(typed) == pattern
