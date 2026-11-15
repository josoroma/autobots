"""The real API app with an arranged membership, for browser qualification only. Not a product path."""
from __future__ import annotations

import os
import sys
from uuid import UUID

import uvicorn
from autobots.api.app import create_app
from autobots.api.resources import AppResources
from autobots.api.settings import load_settings


class FixtureMembership:
    def __init__(self, user: str, workspace: str) -> None:
        self.allowed = (UUID(user), UUID(workspace))

    async def is_member(self, user_id: UUID, workspace_id: UUID) -> bool:
        return (user_id, workspace_id) == self.allowed

    async def workspaces_for(self, user_id: UUID) -> list[UUID]:
        return [self.allowed[1]] if user_id == self.allowed[0] else []

    async def role_in(self, user_id: UUID, workspace_id: UUID) -> str | None:
        return 'owner' if await self.is_member(user_id, workspace_id) else None


def main() -> None:
    membership = FixtureMembership(os.environ['AUTOBOTS_TEST_USER_A'], os.environ['AUTOBOTS_TEST_WORKSPACE_A'])
    uvicorn.run(create_app(AppResources(load_settings(), membership=membership)), host='127.0.0.1', port=int(sys.argv[1]), log_level='warning')


if __name__ == '__main__':
    main()
