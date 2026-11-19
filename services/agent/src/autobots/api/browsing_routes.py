"""Settings → Browsing behind the BFF, Decision 0035 Y1 to Y4: every member reads the YOLO setting,
and only the owner changes it or marks Home's notice seen."""

from fastapi import APIRouter, Depends, Request

from autobots.api.dependencies import CurrentUser, MemberWorkspace, OwnerWorkspace, is_owner
from autobots.api.resources import request_pool
from autobots.api.security import require_internal
from autobots.application import browsing_settings
from autobots.application.browsing_settings import BrowsingSetting
from autobots.contracts.browsing_settings import BrowsingSettingsDraft, BrowsingSettingsView

router = APIRouter(prefix="/v1", dependencies=[Depends(require_internal)])


def _view(setting: BrowsingSetting, owner: bool) -> BrowsingSettingsView:
    return BrowsingSettingsView(
        schema_version=1,
        yolo=setting.yolo,
        version=setting.version,
        notice_pending=owner and setting.yolo and not setting.notice_seen,
        viewer_can_change=owner,
    )


@router.get(
    "/settings/browsing", operation_id="getBrowsingSettings", response_model=BrowsingSettingsView
)
async def get_browsing_settings(
    request: Request, user_id: CurrentUser, workspace_id: MemberWorkspace
) -> BrowsingSettingsView:
    owner = await is_owner(request, user_id, workspace_id)
    async with request_pool(request).connection() as connection:
        return _view(await browsing_settings.load(connection, workspace_id), owner)


@router.put(
    "/settings/browsing", operation_id="putBrowsingSettings", response_model=BrowsingSettingsView
)
async def put_browsing_settings(
    body: BrowsingSettingsDraft, request: Request, workspace_id: OwnerWorkspace
) -> BrowsingSettingsView:
    """Y4: turning it off applies at every run's next browse, and on to runs admitted after."""
    async with request_pool(request).connection() as connection:
        saved = await browsing_settings.change(
            connection, workspace_id, body.yolo, body.expected_version
        )
    return _view(saved, True)


@router.post(
    "/settings/browsing/notice",
    operation_id="markBrowsingNoticeSeen",
    response_model=BrowsingSettingsView,
)
async def mark_browsing_notice_seen(
    request: Request, workspace_id: OwnerWorkspace
) -> BrowsingSettingsView:
    """Y1: Home shows the notice once. Marking it again changes nothing."""
    async with request_pool(request).connection() as connection:
        return _view(await browsing_settings.notice_seen(connection, workspace_id), True)
