import { api } from "@/api/client";

export interface Card {
  boardId: number;
  cardId: number;
  customId: string | null;
  title: string;
  url: string;
  state: "active" | "archived" | "discarded";
  status: string;
  statusLabel: string;
  columnId: number | null;
  columnName: string | null;
  laneId: number | null;
  laneName: string | null;
  workflowName: string | null;
  section: number | null;
  ownerUserId: number | null;
  ownerName: string | null;
  coOwnerNames: string[];
  typeId: number | null;
  typeName: string | null;
  size: number | null;
  priority: number;
  priorityLabel: string;
  deadline: string | null;
  createdAt: string | null;
  lastModified: string | null;
  firstStartTime: string | null;
  endTime: string | null;
  archivedAt: string | null;
  isBlocked: boolean;
  blockReason: { label: string | null; comment: string | null } | null;
  currentBlockTimeSeconds: number | null;
  overdue: boolean;
  dueSoon: boolean;
  missing: boolean;
}

export interface CardTransition {
  column_id: number | null;
  lane_id: number | null;
  start: string | null;
  end: string | null;
  columnName: string | null;
  laneName: string | null;
}

export interface CardEvent {
  occurredAt: string;
  type: string;
  field?: string;
  fieldLabel?: string;
  from?: unknown;
  to?: unknown;
  fromLabel?: string | null;
  toLabel?: string | null;
  source?: string;
}

export interface CardDetail extends Card {
  transitions: CardTransition[];
  events: CardEvent[];
  dataAsOf: string | null;
  firstEndTime: string | null;
  lastEndTime: string | null;
  inCurrentPositionSince: string | null;
  loggedTimeSeconds: number | null;
  eventsSince?: string | null;
  snapshotsSince?: string | null;
}

export interface CardPage {
  items: Card[];
  total: number;
  page: number;
  pageSize: number;
  dataAsOf: string | null;
}

export interface Option<T = number | string> {
  value: T;
  label: string;
}

export interface FilterOptions {
  statuses: Option<string>[];
  priorities: Option<number>[];
  columns: Option<number>[];
  lanes: Option<number>[];
  types: Option<number>[];
  owners: Option<number>[];
}

/** Filtros aceites pela API (mesmos nomes dos parâmetros de query). */
export const CARD_FILTER_KEYS = [
  "q",
  "state",
  "status",
  "columnId",
  "laneId",
  "ownerUserId",
  "unassigned",
  "typeId",
  "priority",
  "blocked",
  "overdue",
  "dueSoon",
  "createdFrom",
  "createdTo",
  "endedFrom",
  "endedTo",
] as const;

export type CardQuery = Partial<Record<(typeof CARD_FILTER_KEYS)[number] | "sort" | "page" | "pageSize", string>>;

export const listCards = (boardId: number, query: CardQuery) =>
  api<CardPage>(`/api/v1/boards/${boardId}/cards`, { query });
export const getCard = (boardId: number, cardId: number) => api<CardDetail>(`/api/v1/boards/${boardId}/cards/${cardId}`);
export const getFilterOptions = (boardId: number) => api<FilterOptions>(`/api/v1/boards/${boardId}/cards/filter-options`);
