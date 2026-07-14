from __future__ import annotations

import uuid

from sqlalchemy import update
from sqlalchemy.engine import Connection

from platform_db.models import MappingWorkspace


def optimistic_rename_workspace(connection: Connection, workspace_id: uuid.UUID, expected_row_version: int, name: str) -> bool:
    result = connection.execute(
        update(MappingWorkspace).where(
            MappingWorkspace.mapping_workspace_id == workspace_id,
            MappingWorkspace.row_version == expected_row_version,
        ).values(workspace_name=name)
    )
    return result.rowcount == 1

