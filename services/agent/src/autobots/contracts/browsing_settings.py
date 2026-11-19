"""Settings → Browsing: the workspace's YOLO setting, Decision 0035 Y1 to Y4."""

from typing import Literal

from pydantic import BaseModel, Field

from autobots.contracts.primitives import STRICT_CONTRACT


class BrowsingSettingsView(BaseModel):
    """Whether a `browse_goal` call may start without approval and type and submit, within its
    Expert's browse domains. `version` is 0 until the setting is first saved. `notice_pending` is
    true only for the owner, until Home's one-time notice has been shown (Y1)."""

    model_config = STRICT_CONTRACT

    schema_version: Literal[1]
    yolo: bool
    version: int = Field(ge=0)
    notice_pending: bool
    viewer_can_change: bool


class BrowsingSettingsDraft(BaseModel):
    """The owner's change, at the version they last read."""

    model_config = STRICT_CONTRACT

    yolo: bool
    expected_version: int = Field(ge=0)
