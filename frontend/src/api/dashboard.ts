import { api } from "@/api/client";
import type { CardQuery } from "@/api/cards";

export type Granularity = "day" | "week" | "month";

export interface PeriodInfo {
  from: string;
  to: string;
  granularity: Granularity;
}

export interface DistributionItem {
  key: string | number | null;
  label: string;
  count: number;
}

export interface TimelinePoint {
  bucket: string;
  label: string;
  created: number;
  completed: number;
}

export interface Dashboard {
  boardId: number;
  dataAsOf: string | null;
  generatedAt: string;
  stale: boolean;
  period: PeriodInfo;
  kpis: Record<
    | "total"
    | "backlog"
    | "todo"
    | "inProgress"
    | "active"
    | "done"
    | "blocked"
    | "overdue"
    | "dueSoon"
    | "unassigned"
    | "createdInPeriod"
    | "completedInPeriod",
    number
  >;
  distributions: Record<"status" | "column" | "lane" | "type" | "priority" | "owner", DistributionItem[]>;
  timeline: TimelinePoint[];
}

/** Parâmetros de período partilhados pelas páginas analíticas. */
export const PERIOD_KEYS = ["from", "to", "granularity"] as const;
export type PeriodQuery = Partial<Record<(typeof PERIOD_KEYS)[number], string>>;

export const getDashboard = (boardId: number, query: CardQuery & PeriodQuery) =>
  api<Dashboard>(`/api/v1/boards/${boardId}/dashboard`, { query });
