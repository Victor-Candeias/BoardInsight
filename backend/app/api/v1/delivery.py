from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import DB, AppSettings
from app.api.v1.common import board_or_404, is_stale
from app.api.v1.dashboard import period_params
from app.api.v1.filters import Filters
from app.services.attention import build_attention
from app.services.cfd import CfdGroup, build_cfd
from app.services.delivery import build_deadlines, build_throughput
from app.services.developers import build_developers
from app.services.flow import build_flow
from app.services.periods import Granularity
from app.services.quality import build_blockers, build_quality

router = APIRouter(prefix="/boards/{board_id}", tags=["delivery"])


@router.get("/throughput")
def throughput(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, granularity = period_params(settings, date_from, date_to, granularity)
    return build_throughput(db, board, filters, period, granularity) | {"stale": is_stale(board, settings)}


@router.get("/deadlines")
def deadlines(board_id: int, db: DB, settings: AppSettings, filters: Filters) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    return build_deadlines(db, board, filters, settings.tz) | {"stale": is_stale(board, settings)}


@router.get("/attention")
def attention(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, _ = period_params(settings, date_from, date_to, "month")
    return build_attention(db, board, filters, period, settings.attention_wip_per_person) | {"stale": is_stale(board, settings)}


@router.get("/developers")
def developers(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, granularity = period_params(settings, date_from, date_to, granularity)
    return build_developers(db, board, filters, period, granularity) | {"stale": is_stale(board, settings)}


@router.get("/flow")
def flow(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, granularity = period_params(settings, date_from, date_to, granularity)
    return build_flow(db, board, filters, period, granularity) | {"stale": is_stale(board, settings)}


@router.get("/cfd")
def cfd(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    group: CfdGroup = "status",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, _ = period_params(settings, date_from, date_to, "day")
    return build_cfd(db, board, filters, period, group) | {"stale": is_stale(board, settings)}


@router.get("/blockers")
def blockers(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, granularity = period_params(settings, date_from, date_to, granularity)
    return build_blockers(db, board, filters, period, granularity) | {"stale": is_stale(board, settings)}


@router.get("/quality")
def quality(
    board_id: int,
    db: DB,
    settings: AppSettings,
    filters: Filters,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> dict[str, Any]:
    board = board_or_404(db, board_id)
    period, granularity = period_params(settings, date_from, date_to, granularity)
    return build_quality(db, board, filters, period, granularity) | {"stale": is_stale(board, settings)}

