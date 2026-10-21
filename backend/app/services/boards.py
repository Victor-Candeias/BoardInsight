"""Leitura de metadados e estrutura dos boards no Businessmap (só leitura)."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.integrations.businessmap import BusinessmapClient, BusinessmapError
from app.models.businessmap import BmBoard, BmCardType, parse_board_structure
from app.models.cards import SECTION_STATUS, STATUS_LABELS

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


SECTION_NAMES = {1: "Backlog", 2: "Pedido", 3: "Em curso", 4: "Concluído", 5: "Arquivo"}
BOARD_DATA_COLLECTIONS = ("cards", "card_events", "board_snapshots", "sync_runs", "users_cache")


def column_mapping(board: dict[str, Any]) -> list[dict[str, Any]]:
    """Mapeamento (só leitura) coluna → secção → estado normalizado, por workflow."""
    structure = board.get("structure") or {}
    workflows = {w["workflowId"]: w.get("name") for w in structure.get("workflows", [])}
    columns = structure.get("columns", [])
    by_id = {c["columnId"]: c for c in columns}
    cycle = set(board.get("cycleTimeColumnIds") or [])
    rows = []
    for c in columns:
        parent = by_id.get(c.get("parentColumnId"))
        status = SECTION_STATUS.get(c.get("section") or 0, "unknown")
        rows.append(
            {
                "columnId": c["columnId"],
                "name": c.get("name"),
                "parentName": parent.get("name") if parent else None,
                "workflowId": c.get("workflowId"),
                "workflowName": workflows.get(c.get("workflowId")),
                "section": c.get("section"),
                "sectionName": SECTION_NAMES.get(c.get("section") or 0, "Desconhecida"),
                "status": status,
                "statusLabel": STATUS_LABELS[status],
                "cycleTime": c["columnId"] in cycle,
                "wipLimit": c.get("limit"),
                "position": c.get("position"),
            }
        )
    return rows


async def test_connection(client: BusinessmapClient, board_id: int) -> dict[str, Any]:
    """Verifica cada recurso de leitura usado pelo BoardInsight (README §2: metadados ≠ cartões)."""
    checks: list[dict[str, Any]] = []
    board_name: str | None = None

    async def check(name: str, label: str, call: Callable[[], Awaitable[Any]], required: bool = True) -> Any:
        try:
            value = await call()
        except BusinessmapError as exc:
            checks.append({"name": name, "label": label, "ok": False, "required": required, "code": exc.code, "message": exc.message})
            return None
        checks.append({"name": name, "label": label, "ok": True, "required": required})
        return value

    board = await check("board", "Metadados do board", lambda: client.get_board(board_id))
    if board is not None:
        board_name = BmBoard.model_validate(board).name
        await check("structure", "Estrutura (colunas/lanes)", lambda: client.get_board_structure(board_id))
        await check("cards", "Cartões ativos", lambda: client.list_cards(board_id, per_page=1))
        await check("archived", "Cartões arquivados", lambda: client.list_cards(board_id, state="archived", per_page=1), required=False)
        await check("cycle_time", "Colunas de cycle time", lambda: client.get_cycle_time_columns(board_id), required=False)
        await check("users", "Utilizadores", client.get_users, required=False)
        await check("card_types", "Tipos de cartão", client.get_card_types, required=False)
    return {
        "boardId": board_id,
        "boardName": board_name,
        "ok": all(c["ok"] for c in checks if c["required"]),
        "checks": checks,
        "rateLimit": {"perMinuteRemaining": client.rate_limit.per_minute_remaining, "perHourRemaining": client.rate_limit.per_hour_remaining},
    }
