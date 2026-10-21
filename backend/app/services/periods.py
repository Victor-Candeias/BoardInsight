"""Buckets de tempo (dia / semana ISO / mês) na timezone de apresentação."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from app.services.card_query import day_start

Granularity = Literal["day", "week", "month"]
MONTHS_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


@dataclass(frozen=True)
class Period:
    start: date  # inclusivo (dia local)
    end: date  # inclusivo (dia local)
    tz: ZoneInfo

    @property
    def start_utc(self) -> datetime:
        return day_start(self.start, self.tz)

    @property
    def end_utc(self) -> datetime:
        return day_start(self.end + timedelta(days=1), self.tz)

    def contains(self, value: datetime | None) -> bool:
        return value is not None and self.start_utc <= value < self.end_utc


def default_period(tz: ZoneInfo, *, weeks: int = 12, today: date | None = None) -> tuple[date, date]:
    today = today or datetime.now(tz).date()
    return today - timedelta(weeks=weeks) + timedelta(days=1), today


def bucket_start(day: date, granularity: Granularity) -> date:
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def bucket_of(value: datetime, granularity: Granularity, tz: ZoneInfo) -> date:
    return bucket_start(value.astimezone(tz).date(), granularity)


def next_bucket(start: date, granularity: Granularity) -> date:
    if granularity == "week":
        return start + timedelta(weeks=1)
    if granularity == "month":
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def buckets(period: Period, granularity: Granularity) -> list[date]:
    out = []
    current = bucket_start(period.start, granularity)
    while current <= period.end:
        out.append(current)
        current = next_bucket(current, granularity)
    return out


def bucket_label(start: date, granularity: Granularity) -> str:
    if granularity == "week":
        year, week, _ = start.isocalendar()
        return f"{year}-S{week:02d}"
    if granularity == "month":
        return f"{MONTHS_PT[start.month - 1]} {start.year}"
    return start.strftime("%d/%m")
