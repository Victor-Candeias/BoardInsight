"""Leitura de metadados e estrutura dos boards no Businessmap (só leitura)."""

import logging
from typing import Any

from app.integrations.businessmap import BusinessmapClient, BusinessmapError
from app.models.businessmap import BmBoard, BmCardType, parse_board_structure

logger = logging.getLogger(__name__)


async def fetch_board_metadata(client: BusinessmapClient, board_id: int) -> dict[str, Any]:
    """Metadados + estrutura (colunas/lanes/secções) + colunas de cycle time + tipos de cartão."""
    board = BmBoard.model_validate(await client.get_board(board_id))
    structure = parse_board_structure(await client.get_board_structure(board_id))
    warnings: list[str] = []

    cycle_time_column_ids: list[int] = []
    try:
        for wf in await client.get_cycle_time_columns(board_id):
            cycle_time_column_ids += [int(c["column_id"]) for c in wf.get("effective_cycle_time_columns") or []]
    except BusinessmapError as exc:
        warnings.append(f"colunas de cycle time indisponíveis ({exc.code})")

    card_types: list[dict[str, Any]] = []
    try:
        for raw in await client.get_card_types():
            t = BmCardType.model_validate(raw)
            card_types.append({"typeId": t.type_id, "name": t.name or f"Tipo {t.type_id}", "color": t.color})
    except BusinessmapError as exc:
        warnings.append(f"tipos de cartão indisponíveis ({exc.code})")

    return {
        "name": board.name,
        "workspaceId": board.workspace_id,
        "isArchived": board.is_archived,
        "structure": {
            "workflows": [{"workflowId": w.workflow_id, "name": w.name, "type": w.type} for w in structure.workflows],
            "columns": [
                {
                    "columnId": c.column_id,
                    "workflowId": c.workflow_id,
                    "name": c.name,
                    "section": c.section,
                    "parentColumnId": c.parent_column_id,
                    "position": c.position,
                    "limit": c.limit,
                }
                for c in structure.columns
            ],
            "lanes": [{"laneId": lane.lane_id, "workflowId": lane.workflow_id, "name": lane.name, "position": lane.position} for lane in structure.lanes],
        },
        "cycleTimeColumnIds": cycle_time_column_ids,
        "cardTypes": card_types,
        "metadataWarnings": warnings,
    }
