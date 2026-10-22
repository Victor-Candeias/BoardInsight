"""Exportação dos cartões filtrados (F1): CSV (Excel PT: `;` e vírgula decimal) e JSON."""

import csv
import io
import json
from collections.abc import Iterable, Iterator
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.models.cards import PRIORITY_LABELS
from app.services.card_query import CLOSED_STATUSES, aging_days

ExportFormat = Literal["csv", "json"]

# (chave JSON, cabeçalho CSV, tipo)
COLUMNS: list[tuple[str, str, str]] = [
    ("cardId", "ID", "int"),
    ("customId", "ID personalizado", "text"),
    ("title", "Título", "text"),
    ("status", "Estado", "text"),
    ("columnName", "Coluna", "text"),
    ("laneName", "Lane", "text"),
    ("workflowName", "Workflow", "text"),
    ("typeName", "Tipo", "text"),
    ("ownerName", "Responsável", "text"),
    ("coOwnerNames", "Co-responsáveis", "list"),
    ("priority", "Prioridade", "text"),
    ("size", "Tamanho", "number"),
    ("deadline", "Prazo", "datetime"),
    ("overdue", "Em atraso", "bool"),
    ("isBlocked", "Bloqueado", "bool"),
    ("blockReason", "Motivo do bloqueio", "text"),
    ("createdAt", "Criado em", "datetime"),
    ("firstStartTime", "Início", "datetime"),
    ("endTime", "Fim", "datetime"),
    ("leadTimeDays", "Lead time (dias)", "number"),
    ("cycleTimeDays", "Cycle time (dias)", "number"),
    ("agingDays", "Idade em curso (dias)", "number"),
    ("state", "Estado no Businessmap", "text"),
    ("missing", "Em falta na última sync", "bool"),
]
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _days(start: datetime | None, end: datetime | None) -> float | None:
    return round((end - start).total_seconds() / 86400, 2) if start and end else None


def export_row(card: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Cartão enriquecido (CardEnricher) → linha de exportação com chaves estáveis."""
    reason = card.get("blockReason") or {}
    aging = aging_days(card, now)[0] if card.get("status") == "in_progress" else None
    return {
        "cardId": card["cardId"],
        "customId": card.get("customId"),
        "title": card.get("title"),
        "status": card.get("statusLabel"),
        "columnName": card.get("columnName"),
        "laneName": card.get("laneName"),
        "workflowName": card.get("workflowName"),
        "typeName": card.get("typeName"),
        "ownerName": card.get("ownerName"),
        "coOwnerNames": [n for n in card.get("coOwnerNames") or [] if n],
        "priority": PRIORITY_LABELS.get(card.get("priority")),
        "size": card.get("size"),
        "deadline": card.get("deadline"),
        "overdue": card.get("overdue", False),
        "isBlocked": bool(card.get("isBlocked")),
        "blockReason": (reason.get("label") or reason.get("comment")) if card.get("isBlocked") else None,
        "createdAt": card.get("createdAt"),
        "firstStartTime": card.get("firstStartTime"),
        "endTime": card.get("endTime"),
        "leadTimeDays": _days(card.get("createdAt"), card.get("endTime")),
        "cycleTimeDays": _days(card.get("firstStartTime"), card.get("endTime")),
        "agingDays": round(aging, 2) if aging is not None and card.get("status") not in CLOSED_STATUSES else None,
        "state": card.get("state"),
        "missing": card.get("missing", False),
    }


def _safe_text(value: str) -> str:
    """Evita injeção de fórmulas ao abrir o CSV numa folha de cálculo."""
    return "'" + value if value.startswith(FORMULA_PREFIXES) else value


def _csv_cell(value: Any, kind: str, tz: ZoneInfo) -> str:
    if value is None:
        return ""
    if kind == "bool":
        return "Sim" if value else "Não"
    if kind == "datetime":
        return value.astimezone(tz).strftime("%Y-%m-%d %H:%M")
    if kind == "number":
        return str(value).replace(".", ",")
    if kind == "list":
        return _safe_text(", ".join(value))
    if kind == "int":
        return str(value)
    return _safe_text(str(value))


def csv_stream(rows: Iterable[dict[str, Any]], tz: ZoneInfo) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")

    def flush() -> str:
        out = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate()
        return out

    writer.writerow([h for _, h, _ in COLUMNS])
    yield "\ufeff" + flush()  # BOM: o Excel deteta UTF-8
    for row in rows:
        writer.writerow([_csv_cell(row[k], kind, tz) for k, _, kind in COLUMNS])
        yield flush()


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"não serializável: {type(value)}")


def json_stream(rows: Iterable[dict[str, Any]], meta: dict[str, Any]) -> Iterator[str]:
    head = json.dumps(meta, default=_json_default, ensure_ascii=False)
    yield head[:-1] + ', "items": ['
    for i, row in enumerate(rows):
        yield ("," if i else "") + json.dumps(row, default=_json_default, ensure_ascii=False)
    yield "]}"
