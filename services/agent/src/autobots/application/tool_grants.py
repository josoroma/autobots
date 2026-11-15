"""Who a tool is granted to in this workspace (PRD-Studio TL-02).

An Expert counts when its latest version grants the tool; an older version's grant doesn't.
A workflow counts when its published version has an agent step whose Expert grants the tool now.
"""

from uuid import UUID

from autobots.application.sql import SqlConnection, all_rows
from autobots.persistence.rows import GrantedToRow


async def tool_grants(
    connection: SqlConnection, workspace_id: UUID, tool_id: str
) -> tuple[list[tuple[UUID, str, int]], list[tuple[UUID, str, int]]]:
    """Each Expert and workflow it is granted to, as (id, name, latest version), by name."""
    granted = await all_rows(
        connection,
        GrantedToRow,
        "select e.id, e.name, e.latest_version from public.experts e "
        "join public.expert_versions v on v.expert_id = e.id and v.version = e.latest_version "
        "where e.workspace_id = %s and v.config -> 'tools' ? %s order by e.name",
        (workspace_id, tool_id),
    )
    experts = [(row.id, str(row.name), int(row.latest_version)) for row in granted]
    if not experts:
        return [], []
    using = await all_rows(
        connection,
        GrantedToRow,
        "select w.id, w.name, w.latest_version from public.workflows w "
        "join public.workflow_versions v on v.workflow_id = w.id and v.version = w.latest_version "
        "where w.workspace_id = %s and w.latest_version >= 1 and exists ("
        "select 1 from jsonb_array_elements(v.graph -> 'nodes') n "
        "where n ->> 'block' = 'agent' and n -> 'config' ->> 'expert_id' = any(%s)) "
        "order by w.name",
        (workspace_id, [str(item[0]) for item in experts]),
    )
    workflows = [(row.id, str(row.name), int(row.latest_version)) for row in using]
    return experts, workflows
