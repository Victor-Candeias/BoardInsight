"""Sprints por intervalos de datas (E5): velocity, compromisso e burndown.

A API do Businessmap não tem sprints: cada board define uma lista explícita (prevalece) ou uma cadência fixa.
Compromisso = cartões todo/in_progress no primeiro snapshot do primeiro dia da sprint; burndown = desses,
os que continuam em backlog/todo/in_progress no último snapshot de cada dia.
"""

from datetime import date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pymongo.database import Database

from app.models.cards import STATUS_LABELS
from app.repositories.base import utcnow
from app.services.card_query import CardFilters
from app.services.cfd import stable_filter_ids
from app.services.delivery import completed_query
from app.services.periods import Period, bucket_of

MAX_CADENCE_SPRINTS = 26
OPEN_STATUSES = ("backlog", "todo", "in_progress")


class SprintCadence(BaseModel):
    start: date
    lengthDays: int = Field(ge=1, le=90)
    namePrefix: str = Field("Sprint", min_length=1, max_length=40)


class ExplicitSprint(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    start: date
    end: date

    @model_validator(mode="after")
    def check_dates(self) -> "ExplicitSprint":
        if self.end < self.start:
            raise ValueError("a data de fim tem de ser igual ou posterior à de início")
        return self


class SprintConfig(BaseModel):
    cadence: SprintCadence | None = None
    explicit: list[ExplicitSprint] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def check_overlap(self) -> "SprintConfig":
        ordered = sorted(self.explicit, key=lambda s: s.start)
        for prev, cur in zip(ordered, ordered[1:], strict=False):
            if cur.start <= prev.end:
                raise ValueError(f"as sprints '{prev.name}' e '{cur.name}' sobrepõem-se")
        return self

    def to_document(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def list_sprints(config: dict[str, Any] | None, today: date) -> list[dict[str, Any]]:
    """Sprints ordenadas da mais antiga para a mais recente; inclui a atual, exclui futuras na cadência."""
    config = config or {}
    explicit = config.get("explicit") or []
    out: list[dict[str, Any]] = []
    if explicit:
        for s in sorted(explicit, key=lambda s: s["start"]):
            out.append({"name": s["name"], "start": date.fromisoformat(s["start"]), "end": date.fromisoformat(s["end"])})
    elif config.get("cadence"):
        cadence = config["cadence"]
        start, length = date.fromisoformat(cadence["start"]), int(cadence["lengthDays"])
        if start <= today:
            current = (today - start).days // length
            first = max(0, current - MAX_CADENCE_SPRINTS + 1)
            for n in range(first, current + 1):
                s = start + timedelta(days=n * length)
                out.append({"name": f"{cadence.get('namePrefix') or 'Sprint'} {n + 1}", "start": s, "end": s + timedelta(days=length - 1)})
    for s in out:
        s["id"] = s["start"].isoformat()
        s["state"] = "future" if s["start"] > today else "current" if s["end"] >= today else "past"
    return out


def _snapshots(db: Database, board_id: int, period: Period) -> list[dict[str, Any]]:
    return list(
        db.board_snapshots.find(
            {"boardId": board_id, "capturedAt": {"$gte": period.start_utc, "$lt": period.end_utc}},
            {"_id": 0, "capturedAt": 1, "cardIds": 1},
        ).sort("capturedAt", 1)
    )


def _ids(snap: dict[str, Any], statuses: tuple[str, ...]) -> set[int]:
    ids = snap.get("cardIds") or {}
    return {i for s in statuses for i in ids.get(s, [])}


def _sprint_metrics(
    db: Database, board_id: int, sprint: dict[str, Any], filters: CardFilters, tz, now: datetime, detail: bool
) -> dict[str, Any]:
    period = Period(sprint["start"], sprint["end"], tz)
    allowed = stable_filter_ids(db, board_id, filters, period, now)
    completed = list(db.cards.find(completed_query(board_id, filters, period, now), {"_id": 0, "cardId": 1, "size": 1}))
    completed_ids = {c["cardId"] for c in completed}
    out: dict[str, Any] = {
        "id": sprint["id"],
        "name": sprint["name"],
        "start": sprint["start"].isoformat(),
        "end": sprint["end"].isoformat(),
        "state": sprint["state"],
        "completed": len(completed),
        "completedSize": sum(c.get("size") or 0 for c in completed),
    }
    snaps = _snapshots(db, board_id, period)
    first = snaps[0] if snaps else None
    if first is None or bucket_of(first["capturedAt"], "day", tz) != sprint["start"]:
        out |= {"commitmentAvailable": False, "commitmentReason": "sem snapshot no primeiro dia da sprint", "committed": None, "committedDone": None, "completionRate": None}
        if detail:
            out |= {"burndown": [], "commitment": [], "added": []}
        return out

    committed = _ids(first, ("todo", "in_progress"))
    if allowed is not None:
        committed &= allowed
    committed_done = committed & completed_ids
    out |= {
        "commitmentAvailable": True,
        "commitmentAt": first["capturedAt"],
        "committed": len(committed),
        "committedDone": len(committed_done),
        "completionRate": round(len(committed_done) / len(committed), 4) if committed else None,
    }
    if not detail:
        return out

    last_per_day: dict[date, dict[str, Any]] = {}
    for snap in snaps:
        last_per_day[bucket_of(snap["capturedAt"], "day", tz)] = snap
    cards = {c["cardId"]: c for c in db.cards.find({"boardId": board_id, "cardId": {"$in": list(committed)}}, {"_id": 0})}
    sizes = {i: (cards.get(i, {}).get("size") or 0) for i in committed}
    total_days = (sprint["end"] - sprint["start"]).days
    burndown = []
    day = sprint["start"]
    while day <= min(sprint["end"], now.astimezone(tz).date()):
        snap = last_per_day.get(day)
        remaining = committed & _ids(snap, OPEN_STATUSES) if snap else None
        ideal = len(committed) * (1 - (day - sprint["start"]).days / total_days) if total_days else 0
        burndown.append(
            {
                "date": day.isoformat(),
                "remaining": len(remaining) if remaining is not None else None,
                "remainingSize": sum(sizes[i] for i in remaining) if remaining is not None else None,
                "ideal": round(ideal, 2),
            }
        )
        day += timedelta(days=1)

    later = set().union(*(_ids(s, ("todo", "in_progress", "done")) for s in snaps[1:])) if len(snaps) > 1 else set()
    added = later - committed - _ids(first, ("done",))
    if allowed is not None:
        added &= allowed
    added_cards = {c["cardId"]: c for c in db.cards.find({"boardId": board_id, "cardId": {"$in": list(added)}}, {"_id": 0})}

    def row(card_id: int, card: dict[str, Any]) -> dict[str, Any]:
        return {
            "cardId": card_id,
            "customId": card.get("customId"),
            "title": card.get("title"),
            "status": card.get("status"),
            "statusLabel": STATUS_LABELS.get(card.get("status")),
            "size": card.get("size"),
            "doneInSprint": card_id in completed_ids,
        }

    out |= {
        "burndown": burndown,
        "commitment": sorted((row(i, cards.get(i, {})) for i in committed), key=lambda r: (r["doneInSprint"], r["cardId"])),
        "added": sorted((row(i, added_cards.get(i, {})) for i in added), key=lambda r: r["cardId"]),
        "committedSize": sum(sizes.values()),
    }
    return out


def build_sprints(db: Database, board: dict[str, Any], filters: CardFilters, tz, now: datetime | None = None) -> dict[str, Any]:
    now = now or utcnow()
    sprints = list_sprints(board.get("sprints"), now.astimezone(tz).date())
    rows = [_sprint_metrics(db, board["boardId"], s, filters, tz, now, detail=False) for s in sprints if s["state"] != "future"]
    past = [r["completed"] for r in rows if r["state"] == "past"][-3:]
    return {
        "boardId": board["boardId"],
        "dataAsOf": board.get("lastSuccessfulSyncAt"),
        "config": board.get("sprints") or {"cadence": None, "explicit": []},
        "sprints": rows,
        "upcoming": [{"id": s["id"], "name": s["name"], "start": s["start"].isoformat(), "end": s["end"].isoformat()} for s in sprints if s["state"] == "future"],
        "averageVelocity": round(sum(past) / len(past), 2) if past else None,
        "averageVelocitySprints": len(past),
    }


def build_sprint(db: Database, board: dict[str, Any], sprint_id: str, filters: CardFilters, tz, now: datetime | None = None) -> dict[str, Any] | None:
    now = now or utcnow()
    for s in list_sprints(board.get("sprints"), now.astimezone(tz).date()):
        if s["id"] == sprint_id:
            return {"boardId": board["boardId"], "dataAsOf": board.get("lastSuccessfulSyncAt")} | _sprint_metrics(
                db, board["boardId"], s, filters, tz, now, detail=True
            )
    return None
