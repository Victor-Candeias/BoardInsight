"""Histórico recolhido em cada sync (E1): eventos de cartões e snapshots do board.

- `card_events`: alterações observadas entre syncs nos `TRACKED_FIELDS` (`source="sync"`, `occurredAt` = momento
  da sync que as observou) e transições de coluna reportadas pela API (`source="api"`, `occurredAt` = início da
  permanência). Cada evento tem um `eventKey` único → reprocessar a mesma sync não duplica eventos.
- `board_snapshots`: contagens por estado/coluna/lane dos cartões ativos e ids por estado (CFD, burndown).
"""

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from pymongo.database import Database

from app.models.cards import SECTION_STATUS, STATUS_LABELS, TRACKED_FIELDS
from app.services.card_query import CardEnricher

SNAPSHOT_STATUSES = ("backlog", "todo", "in_progress", "done")
FIELD_LABELS = {
    "columnId": "Coluna",
    "laneId": "Lane",
    "section": "Secção",
    "status": "Estado",
    "isBlocked": "Bloqueado",
    "ownerUserId": "Responsável",
    "state": "Estado do cartão",
    "created": "Criado",
    "transition": "Coluna (API)",
}
STATE_LABELS = {"active": "Ativo", "archived": "Arquivado", "discarded": "Descartado"}


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value else "-"


def _insert_events(db: Database, events: list[dict[str, Any]]) -> int:
    created = 0
    for event in events:
        result = db.card_events.update_one({"eventKey": event["eventKey"]}, {"$setOnInsert": event}, upsert=True)
        created += result.upserted_id is not None
    return created


def observed_events(board: dict[str, Any], previous: dict[int, dict[str, Any]], current: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    board_id = board["boardId"]
    first_sync = board.get("lastSuccessfulSyncAt") is None
    events = []
    for card in current:
        card_id = card["cardId"]
        before = previous.get(card_id)
        base = {"boardId": board_id, "cardId": card_id, "source": "sync", "observedAt": now}
        if before is None:
            if not first_sync:
                events.append(
                    base
                    | {
                        "eventKey": f"{board_id}:{card_id}:created",
                        "type": "created",
                        "field": "created",
                        "to": card.get("columnId"),
                        "occurredAt": card.get("createdAt") or now,
                    }
                )
            continue
        for field in TRACKED_FIELDS:
            old, new = before.get(field), card.get(field)
            if old == new:
                continue
            events.append(
                base
                | {
                    "eventKey": f"{board_id}:{card_id}:sync:{_iso(now)}:{field}",
                    "type": "field_change",
                    "field": field,
                    "from": old,
                    "to": new,
                    "occurredAt": now,
                    "previousObservedAt": before.get("lastSeenAt"),
                }
            )
    return events


def transition_events(board: dict[str, Any], previous: dict[int, dict[str, Any]], current: list[dict[str, Any]]) -> list[dict[str, Any]]:
    board_id = board["boardId"]
    columns = {c["columnId"]: c for c in (board.get("structure") or {}).get("columns", [])}
    events = []
    for card in current:
        transitions = card.get("transitions") or []
        before = previous.get(card["cardId"])
        # Só reprocessa quando a lista mudou (evita milhares de escritas por sync).
        if not transitions or (before is not None and _same_transitions(before.get("transitions") or [], transitions)):
            continue
        ordered = sorted((t for t in transitions if t.get("start")), key=lambda t: t["start"])
        prev: dict[str, Any] | None = None
        for t in ordered:
            section = t.get("section") or (columns.get(t.get("column_id")) or {}).get("section")
            prev_section = None
            if prev is not None:
                prev_section = prev.get("section") or (columns.get(prev.get("column_id")) or {}).get("section")
            events.append(
                {
                    "boardId": board_id,
                    "cardId": card["cardId"],
                    "eventKey": f"{board_id}:{card['cardId']}:api:{_iso(t['start'])}:{t.get('column_id')}:{t.get('lane_id')}",
                    "source": "api",
                    "type": "transition",
                    "field": "columnId",
                    "from": prev.get("column_id") if prev else None,
                    "to": t.get("column_id"),
                    "fromLaneId": prev.get("lane_id") if prev else None,
                    "toLaneId": t.get("lane_id"),
                    "fromStatus": SECTION_STATUS.get(prev_section) if prev_section else None,
                    "toStatus": SECTION_STATUS.get(section) if section else None,
                    "occurredAt": t["start"],
                }
            )
            prev = t
    return events


def _same_transitions(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> bool:
    key = lambda t: (t.get("column_id"), t.get("lane_id"), _iso(t.get("start")), _iso(t.get("end")))  # noqa: E731

    def norm(items: list[dict[str, Any]]) -> list[tuple]:
        # Mongo guarda milissegundos: comparar truncado.
        return sorted(
            (k[0], k[1], k[2][:23], k[3][:23])
            for k in (key(t) for t in items)
        )

    return norm(a) == norm(b)


def events_hook(db: Database, board: dict[str, Any], previous: dict[int, dict[str, Any]], current: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    observed = _insert_events(db, observed_events(board, previous, current, now))
    from_api = _insert_events(db, transition_events(board, previous, current))
    return {"eventsObserved": observed, "eventsFromApi": from_api}


def build_snapshot(board: dict[str, Any], current: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    active = [c for c in current if c.get("state") == "active"]
    ids: dict[str, list[int]] = {s: [] for s in SNAPSHOT_STATUSES}
    for c in active:
        if c.get("status") in ids:
            ids[c["status"]].append(c["cardId"])
    by_column: dict[int | None, list[int]] = defaultdict(list)
    for c in active:
        by_column[c.get("columnId")].append(c["cardId"])
    counter = lambda key: [  # noqa: E731
        {"key": k, "count": n} for k, n in sorted(Counter(c.get(key) for c in active).items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    ]
    return {
        "boardId": board["boardId"],
        "capturedAt": now,
        "total": len(active),
        "blocked": sum(1 for c in active if c.get("isBlocked")),
        "byStatus": {s: len(v) for s, v in ids.items()},
        "byColumn": [  # cardIds permite aplicar filtros ao CFD por coluna
            {"key": k, "count": len(v), "cardIds": sorted(v)} for k, v in sorted(by_column.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
        ],
        "byLane": counter("laneId"),
        "cardIds": {s: sorted(v) for s, v in ids.items()},
    }


def snapshot_hook(db: Database, board: dict[str, Any], previous: dict[int, dict[str, Any]], current: list[dict[str, Any]], now: datetime) -> dict[str, Any]:
    snapshot = build_snapshot(board, current, now)
    db.board_snapshots.update_one({"boardId": snapshot["boardId"], "capturedAt": now}, {"$setOnInsert": snapshot}, upsert=True)
    return {"snapshotCards": snapshot["total"]}


def history_since(db: Database, board_id: int) -> dict[str, datetime | None]:
    """Início da recolha (a UI mostra-o: eventos e snapshots só existem a partir daí)."""
    first_snapshot = db.board_snapshots.find_one({"boardId": board_id}, {"capturedAt": 1}, sort=[("capturedAt", 1)])
    first_event = db.card_events.find_one({"boardId": board_id, "source": "sync"}, {"occurredAt": 1}, sort=[("occurredAt", 1)])
    return {
        "snapshotsSince": first_snapshot["capturedAt"] if first_snapshot else None,
        "eventsSince": first_event["occurredAt"] if first_event else None,
    }


def label_event(event: dict[str, Any], enrich: CardEnricher) -> dict[str, Any]:
    """Nomes legíveis calculados na leitura (colunas/pessoas podem mudar de nome)."""
    field = event.get("field")

    def label(value: Any) -> str | None:
        if value is None:
            return None
        if field in ("columnId", "created", "transition"):
            return enrich.column_name(value) or f"Coluna {value}"
        if field == "laneId":
            return enrich.lanes.get(value) or f"Lane {value}"
        if field == "ownerUserId":
            return enrich.user(value)
        if field == "status":
            return STATUS_LABELS.get(value, value)
        if field == "state":
            return STATE_LABELS.get(value, value)
        if field == "isBlocked":
            return "Sim" if value else "Não"
        return str(value)

    return {
        **event,
        "fieldLabel": FIELD_LABELS.get(field or "", field),
        "fromLabel": label(event.get("from")),
        "toLabel": label(event.get("to")),
    }
