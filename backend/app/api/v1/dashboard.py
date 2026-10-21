from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import DB, AppSettings
from app.api.errors import ApiError
from app.api.v1.common import board_or_404, is_stale
from app.api.v1.filters import Filters
from app.services.dashboard import build_dashboard
from app.services.periods import Granularity, Period, buckets, default_period

router = APIRouter(prefix="/boards/{board_id}", tags=["dashboard"])

MAX_BUCKETS = 400


def period_params(
    settings: AppSettings,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "week",
) -> tuple[Period, Granularity]:
    default_from, default_to = default_period(settings.tz)
    period = Period(date_from or default_from, date_to or default_to, settings.tz)
    if period.start > period.end:
        raise ApiError(422, "validation_error", "intervalo de datas inválido")
    if len(buckets(period, granularity)) > MAX_BUCKETS:
        raise ApiError(422, "validation_error", "período demasiado longo para a granularidade escolhida")
    return period, granularity


@router.get("/dashboard")
def dashboard(
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
    result = build_dashboard(db, board, filters, period, granularity)
    result["stale"] = is_stale(board, settings)
    return result
