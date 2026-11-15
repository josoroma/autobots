"""One shape for every refusal whose code reaches a response (refactor plan R-41, PDOM-13, XERR-07).

A refusal has a stable `code`, safe to show, and a `kind` saying what sort of refusal it is. The
kind carries no status: api/errors.py turns it into one. `detail` is internal text, for logs and
tests only, and no response shows it. Signals that never reach a response, such as a lost lease or
a provider failure, keep their own classes.
"""

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import ClassVar


class RefusalKind(StrEnum):
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID = "invalid"
    FORBIDDEN = "forbidden"
    UNAVAILABLE = "unavailable"


class Refusal(Exception):
    """A typed reason something was refused, and nothing changed.

    The code is the class's own, or the first argument where a family raises several. The kind is
    the class's, unless `kinds` names one for this code or the raise passes one, as a request that
    named a refused profile does (PolicyNotOffered).
    """

    code: str = "refused"
    kind: RefusalKind = RefusalKind.CONFLICT
    kinds: ClassVar[Mapping[str, RefusalKind]] = MappingProxyType({})

    def __init__(
        self,
        code: str | None = None,
        *,
        kind: RefusalKind | None = None,
        detail: str | None = None,
    ) -> None:
        if code is not None:
            self.code = code
        self.kind = kind or self.kinds.get(self.code, type(self).kind)
        self.detail = detail
        # The message is the detail, else the code, so a log or a test reads what was raised.
        super().__init__(self.code if detail is None else detail)


class FixedRefusal(Refusal):
    """A refusal whose class names its one code, so its argument is only the internal detail."""

    def __init__(self, detail: str | None = None, *, kind: RefusalKind | None = None) -> None:
        super().__init__(kind=kind, detail=detail)
