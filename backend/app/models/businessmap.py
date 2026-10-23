"""DTOs das respostas da API Businessmap v2 (OpenAPI da instância cttv8, A1).

São tolerantes: campos desconhecidos são ignorados, campos em falta ficam `None`,
strings vazias/datas inválidas passam a `None`. O schema de `transitions` não está
documentado no OpenAPI; aceitam-se os nomes de campos mais prováveis (validar com A2).
"""

from datetime import UTC, datetime
from datetime import date as date_type
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class BmModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    @field_validator("*", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any, info: ValidationInfo) -> Any:
        if isinstance(value, str) and (not value.strip() or value.startswith("0000-00-00")):
            # Campos de texto obrigatórios mantêm "", os restantes passam a None.
            return "" if cls.model_fields[info.field_name].annotation is str else None
        return value


class BmBoard(BmModel):
    board_id: int
    workspace_id: int | None = None
    name: str = ""
    is_archived: bool = False
    revision: int | None = None


class BmUser(BmModel):
    user_id: int
    username: str | None = None
    realname: str | None = None

    @property
    def display_name(self) -> str:
        return self.realname or self.username or f"Utilizador {self.user_id}"


class BmCardType(BmModel):
    type_id: int
    name: str | None = None
    color: str | None = None


class BmBlockReason(BmModel):
    block_type: int | None = None
    reason_id: int | None = None
    label: str | None = None
    comment: str | None = None


class BmTransition(BmModel):
    workflow_id: int | None = None
    column_id: int | None = None
    lane_id: int | None = None
    section: int | None = None
    start: datetime | None = Field(default=None, validation_alias=AliasChoices("start", "start_time", "entered_at", "from"))
    end: datetime | None = Field(default=None, validation_alias=AliasChoices("end", "end_time", "left_at", "to"))


class BmCard(BmModel):
    card_id: int
    board_id: int
    custom_id: str | None = None
    workflow_id: int | None = None
    title: str = ""
    owner_user_id: int | None = None
    co_owner_ids: list[int] = Field(default_factory=list)
    type_id: int | None = None
    size: float | None = None
    priority: int | None = None
    color: str | None = None
    deadline: datetime | None = None
    created_at: datetime | None = None
    revision: int | None = None
    last_modified: datetime | None = None
    in_current_position_since: datetime | None = None
    section: int | None = None
    column_id: int | None = None
    lane_id: int | None = None
    position: int | None = None
    last_column_id: int | None = None
    last_lane_id: int | None = None
    archived_at: datetime | None = None
    discarded_at: datetime | None = None
    is_blocked: bool = False
    block_reason: BmBlockReason | None = None
    current_block_time: int | None = None
    current_logged_time: int | None = None
    current_cycle_time: int | None = None
    first_request_time: datetime | None = None
    first_start_time: datetime | None = None
    first_end_time: datetime | None = None
    last_request_time: datetime | None = None
    last_start_time: datetime | None = None
    last_end_time: datetime | None = None
    tag_ids: list[int] = Field(default_factory=list)
    transitions: list[BmTransition] = Field(default_factory=list)

    @field_validator("co_owner_ids", "tag_ids", "transitions", mode="before")
    @classmethod
    def _none_to_list(cls, value: Any) -> Any:
        return [] if value is None else value

    @field_validator("block_reason", mode="before")
    @classmethod
    def _empty_block_reason(cls, value: Any) -> Any:
        return None if value in ([], {}, 0) else value


class BmLoggedTime(BmModel):
    """Entrada de `GET /loggedTime`: `date` é o dia do trabalho; `time` em segundos."""

    logged_time_id: int
    card_id: int | None = None
    parent_card_id: int | None = None
    subtask_id: int | None = None
    lane_id: int | None = None
    column_id: int | None = None
    user_id: int | None = None
    category_id: int | None = None
    date: date_type | None = None
    time: int = 0
    comment: str | None = None
    logged_at: datetime | None = None

    @field_validator("subtask_id", "parent_card_id", "category_id", mode="before")
    @classmethod
    def _zero_to_none(cls, value: Any) -> Any:
        return None if value in (0, "0") else value

    @field_validator("time", mode="before")
    @classmethod
    def _none_to_zero(cls, value: Any) -> Any:
        return 0 if value is None else value

    @field_validator("logged_at", mode="after")
    @classmethod
    def _naive_is_utc(cls, value: datetime | None) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


class BmColumn(BmModel):
    column_id: int
    workflow_id: int | None = None
    name: str = ""
    section: int | None = None
    parent_column_id: int | None = None
    position: int = 0
    limit: int | None = None


class BmLane(BmModel):
    lane_id: int
    workflow_id: int | None = None
    name: str = ""
    position: int = 0


class BmWorkflow(BmModel):
    workflow_id: int
    name: str = ""
    type: int | None = None
    is_enabled: bool = True


class BoardStructure(BaseModel):
    workflows: list[BmWorkflow]
    columns: list[BmColumn]
    lanes: list[BmLane]

    def column(self, column_id: int | None) -> BmColumn | None:
        return next((c for c in self.columns if c.column_id == column_id), None)


def parse_board_structure(data: dict[str, Any]) -> BoardStructure:
    """Normaliza `GET /boards/{id}/currentStructure` (dicionários indexados por id)."""
    workflows_raw: dict[str, Any] = data.get("workflows") or {}
    columns_raw: dict[str, Any] = data.get("columns") or {}
    lanes_raw: dict[str, Any] = data.get("lanes") or {}
    order = [int(w) for w in data.get("workflow_order") or workflows_raw.keys()]

    workflows: list[BmWorkflow] = []
    column_position: dict[int, int] = {}
    lane_position: dict[int, int] = {}
    for workflow_id in order:
        wf = workflows_raw.get(str(workflow_id)) or {}
        workflows.append(BmWorkflow(workflow_id=workflow_id, **{k: v for k, v in wf.items() if k != "workflow_id"}))
        ordered = list(dict.fromkeys([*(wf.get("top_columns") or []), *(wf.get("bottom_columns") or [])]))
        for index, column_id in enumerate(ordered):
            column_position.setdefault(int(column_id), index)
        for index, lane_id in enumerate(wf.get("top_lanes") or []):
            lane_position.setdefault(int(lane_id), index)

    columns = []
    for key, col in columns_raw.items():
        column_id = int(key)
        parent = col.get("parent_column_id") or None
        columns.append(
            BmColumn(
                column_id=column_id,
                workflow_id=col.get("workflow_id"),
                name=col.get("name") or "",
                section=col.get("section"),
                parent_column_id=parent,
                position=column_position.get(column_id, 999),
                limit=col.get("limit"),
            )
        )
    # Sub-colunas herdam a secção da coluna pai.
    by_id = {c.column_id: c for c in columns}
    for c in columns:
        if c.section is None and c.parent_column_id in by_id:
            c.section = by_id[c.parent_column_id].section
    lanes = [
        BmLane(lane_id=int(key), workflow_id=lane.get("workflow_id"), name=lane.get("name") or "", position=lane_position.get(int(key), 999))
        for key, lane in lanes_raw.items()
    ]
    columns.sort(key=lambda c: (order.index(c.workflow_id) if c.workflow_id in order else 99, c.position))
    lanes.sort(key=lambda lane: lane.position)
    return BoardStructure(workflows=workflows, columns=columns, lanes=lanes)
