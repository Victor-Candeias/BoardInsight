from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404
from app.api.v1.filters import Filters
from app.models.cards import PRIORITY_LABELS, STATUS_LABELS
from app.repositories.base import utcnow
from app.services.card_query import CardEnricher, build_query, sort_spec
from app.services.export import ExportFormat, csv_stream, export_row, json_stream
from app.services.history import history_since, label_event

router = APIRouter(prefix="/boards/{board_id}/cards", tags=["cards"])

LIST_PROJECTION = {"_id": 0, "raw": 0, "transitions": 0}


@router.get("")
def list_cards(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    sort: str | None = Query(None, description="Campo de ordenação; prefixo `-` para descendente"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    query = build_query(board_id, filters, settings.tz)
    try:
        order = sort_spec(sort)
    except ValueError:
        raise ApiError(422, "validation_error", f"ordenação inválida: {sort}") from None
    total = db.cards.count_documents(query)
    cursor = db.cards.find(query, LIST_PROJECTION).sort(order).skip((page - 1) * page_size).limit(page_size)
    enrich = CardEnricher(db, board)
    return {
        "items": [enrich(c) for c in cursor],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
    }


@router.get("/filter-options")
def filter_options(board_id: int, db: DB) -> dict[str, Any]:
    """Valores possíveis para os filtros (só os que existem nos cartões sincronizados)."""
    board = board_or_404(db, board_id)
    enrich = CardEnricher(db, board)
    base = {"boardId": board_id, "missingSince": None}
    owner_ids = sorted(u for u in db.cards.distinct("ownerUserId", base) if u is not None)
    column_ids = set(db.cards.distinct("columnId", base))
    lane_ids = set(db.cards.distinct("laneId", base))
    type_ids = set(db.cards.distinct("typeId", base))
    columns = (board.get("structure") or {}).get("columns", [])
    return {
        "statuses": [{"value": k, "label": v} for k, v in STATUS_LABELS.items()],
        "priorities": [{"value": k, "label": v} for k, v in PRIORITY_LABELS.items()],
        "columns": [
            {"value": c["columnId"], "label": enrich.column_name(c["columnId"])} for c in columns if c["columnId"] in column_ids
        ],
        "lanes": [{"value": k, "label": v} for k, v in enrich.lanes.items() if k in lane_ids],
        "types": [{"value": k, "label": enrich.types.get(k) or f"Tipo {k}"} for k in sorted(t for t in type_ids if t is not None)],
        "owners": sorted(({"value": u, "label": enrich.user(u)} for u in owner_ids), key=lambda o: o["label"].lower()),
    }


@router.get("/export")
def export_cards(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    format: ExportFormat = "csv",
    sort: str | None = None,
) -> StreamingResponse:
    """Todos os cartões que cumprem os filtros (sem paginação), até `EXPORT_MAX_ROWS`."""
    board = board_or_404(db, board_id)
    query = build_query(board_id, filters, settings.tz)
    try:
        order = sort_spec(sort)
    except ValueError:
        raise ApiError(422, "validation_error", f"ordenação inválida: {sort}") from None
    total = db.cards.count_documents(query)
    if total > settings.export_max_rows:
        raise ApiError(422, "export_too_large", f"{total} cartões excedem o máximo de {settings.export_max_rows}; refine os filtros")
    now = utcnow()
    enrich = CardEnricher(db, board, now)
    rows = (export_row(enrich(c), now) for c in db.cards.find(query, LIST_PROJECTION).sort(order))
    stamp = now.astimezone(settings.tz).strftime("%Y%m%d-%H%M")
    filename = f"boardinsight-board{board_id}-cartoes-{stamp}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"', "X-Total-Count": str(total)}
    if format == "csv":
        return StreamingResponse(csv_stream(rows, settings.tz), media_type="text/csv; charset=utf-8", headers=headers)
    meta = {"boardId": board_id, "exportedAt": now, "dataAsOf": board.get("lastSuccessfulSyncAt"), "total": total}
    return StreamingResponse(json_stream(rows, meta), media_type="application/json", headers=headers)


@router.get("/{card_id}")
def get_card(board_id: int, card_id: int, db: DB) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    card = db.cards.find_one({"boardId": board_id, "cardId": card_id}, {"_id": 0, "raw": 0})
    if card is None:
        raise ApiError(404, "card_not_found", f"cartão {card_id} não encontrado no board {board_id}")
    enrich = CardEnricher(db, board)
    # Cada transição = permanência numa coluna/lane (início/fim).
    transitions = sorted(
        (
            {**t, "columnName": enrich.column_name(t.get("column_id")), "laneName": enrich.lanes.get(t.get("lane_id"))}
            for t in card.get("transitions") or []
        ),
        key=lambda t: (t.get("start") is None, t.get("start") or 0),
    )
    events = [
        label_event(e, enrich)
        # As transições da API já aparecem em `transitions`; aqui só as alterações observadas entre syncs.
        for e in db.card_events.find({"boardId": board_id, "cardId": card_id, "source": {"$ne": "api"}}, {"_id": 0})
        .sort("occurredAt", -1)
        .limit(200)
    ]
    return {
        **enrich(card),
        "transitions": transitions,
        "events": events,
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        **history_since(db, board_id),
    }
