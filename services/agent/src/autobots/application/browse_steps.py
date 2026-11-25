"""A browse's steps and their screenshots, Decision 0035 Y11 and US-17.4.

The worker records each browser-use step of a browse_goal use, with its screenshot in the run's
private storage. Members of the run's workspace read them. The workspace and run come from the
rows, and a screenshot's bytes are checked against their digest before leaving.
"""

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlsplit
from uuid import UUID

from autobots.application.artifacts import ObjectStore
from autobots.application.sql import SqlConnection, all_rows, optional_row
from autobots.application.tool_definitions import ToolScope
from autobots.contracts.browse_steps import BrowseStep, BrowseTouch
from autobots.domain.errors import Refusal, RefusalKind

MEDIA_TYPE = "image/jpeg"


class StepUnavailable(Refusal):
    """Not this workspace's, no such step, no screenshot kept, or altered. No bytes leave."""

    kinds = MappingProxyType({"browse_step_not_found": RefusalKind.NOT_FOUND})


def page_of(url: str | None) -> str | None:
    """A page as host and path, with no query or fragment."""
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    return f"{parts.hostname.lower()}{parts.path or '/'}"[:2048]


def screenshot_path(scope: ToolScope, use_id: int, step: int) -> str:
    """In the run's namespace of the private store, which allows one name below the run."""
    return f"{scope.workspace_id}/{scope.run_id}/browse-{use_id}-{step}.jpg"


async def record_step(
    connection: SqlConnection,
    scope: ToolScope,
    use_id: int,
    step: int,
    *,
    page: str | None,
    submits: tuple[str, ...],
    screenshot: tuple[str, bytes] | None,
    touched: tuple[BrowseTouch, ...] = (),
) -> None:
    """One step's row. `screenshot` is its stored object's path and bytes, or None."""
    path, size, digest = (
        (screenshot[0], len(screenshot[1]), hashlib.sha256(screenshot[1]).hexdigest())
        if screenshot is not None
        else (None, None, None)
    )
    await connection.execute(
        "insert into app_private.browse_steps "
        "(tool_use_id, run_id, workspace_id, step, page, submits, object_path, bytes, sha256, "
        "touched) values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb) "
        "on conflict (tool_use_id, step) do nothing",
        (
            use_id,
            scope.run_id,
            scope.workspace_id,
            step,
            page_of(page),
            json.dumps(list(submits)[:50]),
            path,
            size,
            digest,
            json.dumps([touch.model_dump(mode="json") for touch in touched]),
        ),
    )


@dataclass(frozen=True)
class _StepRow:
    step: int
    page: str | None
    submits: list[str]
    touched: list[dict[str, str]]
    screenshot: bool


@dataclass(frozen=True)
class _ObjectRow:
    object_path: str | None
    sha256: str | None


_OWNED = (
    "from app_private.browse_steps s join app_private.tool_uses u on u.id = s.tool_use_id "
    "where s.workspace_id = %s and s.run_id = %s and s.tool_use_id = %s and u.run_id = s.run_id"
)


async def list_steps(
    connection: SqlConnection, workspace_id: UUID, run_id: UUID, use_id: int
) -> list[BrowseStep]:
    rows = await all_rows(
        connection,
        _StepRow,
        "select s.step, s.page, s.submits, s.touched, s.object_path is not null as screenshot "
        f"{_OWNED} order by s.step",
        (workspace_id, run_id, use_id),
    )
    return [
        BrowseStep(
            step=r.step,
            page=r.page,
            submits=r.submits,
            touched=[BrowseTouch.model_validate(touch) for touch in r.touched],
            screenshot=r.screenshot,
        )
        for r in rows
    ]


async def read_screenshot(
    connection: SqlConnection,
    store: ObjectStore,
    workspace_id: UUID,
    run_id: UUID,
    use_id: int,
    step: int,
) -> bytes:
    row = await optional_row(
        connection,
        _ObjectRow,
        f"select s.object_path, s.sha256 {_OWNED} and s.step = %s",
        (workspace_id, run_id, use_id, step),
    )
    if row is None or row.object_path is None or row.sha256 is None:
        raise StepUnavailable("browse_step_not_found")
    stored = await store.get(row.object_path)
    if stored is None or hashlib.sha256(stored).hexdigest() != row.sha256:
        raise StepUnavailable("browse_step_missing")
    return stored
