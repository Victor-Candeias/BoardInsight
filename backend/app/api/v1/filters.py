from datetime import date
from typing import Annotated

from fastapi import Depends, Query

from app.api.errors import ApiError
from app.services.card_query import CardFilters, StateFilter

STATUSES = {"backlog", "todo", "in_progress", "done", "archived", "discarded", "unknown"}


def card_filters(
    q: Annotated[str | None, Query(max_length=200, description="Pesquisa em título, ID e ID personalizado")] = None,
    state: StateFilter = "active",
    status: Annotated[list[str], Query()] = [],  # noqa: B006 - FastAPI copia o default
    open: Annotated[bool, Query(description="Só cartões abertos (exclui concluídos, arquivados e descartados)")] = False,
    column_id: Annotated[list[int], Query(alias="columnId")] = [],  # noqa: B006
    lane_id: Annotated[list[int], Query(alias="laneId")] = [],  # noqa: B006
    owner_user_id: Annotated[list[int], Query(alias="ownerUserId")] = [],  # noqa: B006
    unassigned: bool = False,
    type_id: Annotated[list[int], Query(alias="typeId")] = [],  # noqa: B006
    priority: Annotated[list[int], Query()] = [],  # noqa: B006
    blocked: bool | None = None,
    overdue: bool = False,
    due_soon: Annotated[bool, Query(alias="dueSoon")] = False,
    created_from: Annotated[date | None, Query(alias="createdFrom")] = None,
    created_to: Annotated[date | None, Query(alias="createdTo")] = None,
    ended_from: Annotated[date | None, Query(alias="endedFrom")] = None,
    ended_to: Annotated[date | None, Query(alias="endedTo")] = None,
    include_missing: Annotated[bool, Query(alias="includeMissing")] = False,
) -> CardFilters:
    if unknown := set(status) - STATUSES:
        raise ApiError(422, "validation_error", f"estado inválido: {', '.join(sorted(unknown))}")
    if any(p not in (1, 2, 3, 4) for p in priority):
        raise ApiError(422, "validation_error", "prioridade deve estar entre 1 e 4")
    for start, end in ((created_from, created_to), (ended_from, ended_to)):
        if start and end and start > end:
            raise ApiError(422, "validation_error", "intervalo de datas inválido")
    return CardFilters(
        q=q,
        state=state,
        status=status,
        open=open,
        column_id=column_id,
        lane_id=lane_id,
        owner_user_id=owner_user_id,
        unassigned=unassigned,
        type_id=type_id,
        priority=priority,
        blocked=blocked,
        overdue=overdue,
        due_soon=due_soon,
        created_from=created_from,
        created_to=created_to,
        ended_from=ended_from,
        ended_to=ended_to,
        include_missing=include_missing,
    )


Filters = Annotated[CardFilters, Depends(card_filters)]
