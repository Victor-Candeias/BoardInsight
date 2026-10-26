from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.api.deps import DB, AppSettings
from app.api.v1.dashboard import period_params
from app.services.logged_times import build_hours_daily_all_boards
from app.services.periods import Granularity

router = APIRouter(prefix="/hours", tags=["hours"])


@router.get("")
def daily_hours_all_boards(
    db: DB,
    settings: AppSettings,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    granularity: Granularity = "day",
    user_id: Annotated[int | None, Query(alias="userId")] = None,
    include_subtasks: Annotated[bool, Query(alias="includeSubtasks")] = True,
) -> dict[str, Any]:
    period, _ = period_params(settings, date_from, date_to, granularity)
    return build_hours_daily_all_boards(db, period, user_id=user_id, include_subtasks=include_subtasks)
