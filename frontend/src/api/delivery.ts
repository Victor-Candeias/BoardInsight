import { api } from "@/api/client";
import type { Card, CardQuery } from "@/api/cards";
import type { DistributionItem, PeriodInfo, PeriodQuery } from "@/api/dashboard";

export interface ThroughputPoint {
  bucket: string;
  label: string;
  count: number;
  size: number;
  partial: boolean;
}

export interface Throughput {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  total: number;
  totalSize: number;
  averagePerBucket: number;
  series: ThroughputPoint[];
  byType: DistributionItem[];
}

export interface DeadlineCard extends Card {
  daysToDeadline: number;
}

export interface DeadlineList {
  total: number;
  items: DeadlineCard[];
  truncated: boolean;
}

export interface Deadlines {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  dueSoonDays: number;
  openTotal: number;
  withoutDeadline: number;
  overdue: DeadlineList;
  dueSoon: DeadlineList;
  overdueByOwner: DistributionItem[];
}

export const getThroughput = (boardId: number, query: CardQuery & PeriodQuery) =>
  api<Throughput>(`/api/v1/boards/${boardId}/throughput`, { query });
export const getDeadlines = (boardId: number, query: CardQuery) => api<Deadlines>(`/api/v1/boards/${boardId}/deadlines`, { query });
