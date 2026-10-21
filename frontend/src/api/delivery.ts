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

export interface DeveloperRow {
  userId: number | null;
  name: string;
  backlog: number;
  todo: number;
  inProgress: number;
  open: number;
  blocked: number;
  overdue: number;
  coOwnedOpen: number;
  completed: number;
  completedSize: number;
  avgAgingDays: number | null;
  maxAgingDays: number | null;
  agingEstimated: boolean;
  completedSeries: number[];
}

export interface Developers {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  buckets: { bucket: string; label: string }[];
  developers: DeveloperRow[];
  disclaimer: string;
}

export const getDevelopers = (boardId: number, query: CardQuery & PeriodQuery) =>
  api<Developers>(`/api/v1/boards/${boardId}/developers`, { query });

export interface MetricSummary {
  available: boolean;
  reason?: string;
  count: number;
  smallSample?: boolean;
  p50?: number;
  p85?: number;
  p95?: number;
  mean?: number;
  min?: number;
  max?: number;
}

export interface AgingItem {
  cardId: number;
  customId: string | null;
  title: string;
  columnName: string | null;
  ownerName: string | null;
  isBlocked: boolean;
  ageDays: number | null;
  estimated: boolean;
  aboveP85: boolean;
}

export interface FlowPoint {
  cardId: number;
  customId: string | null;
  title: string;
  typeName: string | null;
  endTime: string;
  leadDays: number | null;
  cycleDays: number | null;
}

export interface Flow {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  wip: { total: number; blocked: number; byColumn: DistributionItem[]; byLane: DistributionItem[]; byOwner: DistributionItem[] };
  aging: MetricSummary & { threshold: number | null; aboveThreshold: number; estimatedCount: number; items: AgingItem[] };
  leadTime: MetricSummary;
  cycleTime: MetricSummary & { withoutStart: number };
  trend: { bucket: string; label: string; count: number; cycleP50: number | null; cycleP85: number | null; leadP50: number | null }[];
  points: FlowPoint[];
}

export const getFlow = (boardId: number, query: CardQuery & PeriodQuery) => api<Flow>(`/api/v1/boards/${boardId}/flow`, { query });

export type CfdGroup = "status" | "column";

export interface Cfd {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  group: CfdGroup;
  filtered: boolean;
  snapshotsSince: string | null;
  available: boolean;
  reason?: string;
  series: { key: string; label: string }[];
  days: { date: string; capturedAt: string; counts: Record<string, number> }[];
}

export const getCfd = (boardId: number, query: CardQuery & { from?: string; to?: string; group?: string }) =>
  api<Cfd>(`/api/v1/boards/${boardId}/cfd`, { query });

export interface BlockedItem {
  cardId: number;
  customId: string | null;
  title: string;
  status: string;
  columnName: string | null;
  laneName: string | null;
  ownerUserId: number | null;
  ownerName: string | null;
  reason: string | null;
  comment: string | null;
  blockedSeconds: number | null;
  blockedDays: number | null;
}

export type BlockDistribution = DistributionItem & { days: number };

export interface Blockers {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  current: {
    blocked: number;
    openTotal: number;
    share: number | null;
    days: MetricSummary;
    byReason: BlockDistribution[];
    byOwner: BlockDistribution[];
    byColumn: BlockDistribution[];
    items: BlockedItem[];
    truncated: boolean;
  };
  history: {
    historySince: string | null;
    started: number;
    resolved: number;
    resolvedDays: MetricSummary;
    series: { bucket: string; label: string; started: number; resolved: number }[];
  };
}

export interface Quality {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  period: PeriodInfo;
  historySince: string | null;
  available: boolean;
  reason?: string;
  reopens: number;
  reopenedCards: number;
  completed: number;
  reopenRate: number | null;
  series: { bucket: string; label: string; reopens: number }[];
  items: {
    cardId: number;
    customId: string | null;
    title: string | null;
    status: string | null;
    columnName: string | null;
    ownerName: string | null;
    reopens: number;
    lastReopenedAt: string;
  }[];
  truncated: boolean;
}

export const getBlockers = (boardId: number, query: CardQuery & PeriodQuery) =>
  api<Blockers>(`/api/v1/boards/${boardId}/blockers`, { query });
export const getQuality = (boardId: number, query: CardQuery & PeriodQuery) =>
  api<Quality>(`/api/v1/boards/${boardId}/quality`, { query });
