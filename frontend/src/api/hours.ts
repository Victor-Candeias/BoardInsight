import { api } from "@/api/client";
import type { PeriodInfo, PeriodQuery } from "@/api/dashboard";

export const HOURS_KEYS = ["from", "to", "granularity", "userId", "includeSubtasks"] as const;
export type HoursQuery = PeriodQuery & { userId?: string; includeSubtasks?: string };

export interface HoursUserRow {
  userId: number | null;
  name: string;
  seconds: number;
  entries: number;
  cards: number;
  days: number;
  avgSecondsPerDay: number;
  series: number[];
}

export interface HoursEntry {
  loggedTimeId: number;
  date: string;
  userId: number | null;
  userName: string;
  cardId: number | null;
  customId: string | null;
  title: string | null;
  url: string | null;
  subtask: boolean;
  seconds: number;
  comment: string | null;
}

export interface Hours {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  available: boolean;
  warning: string | null;
  period: PeriodInfo;
  buckets: { bucket: string; label: string }[];
  userId: number | null;
  includeSubtasks: boolean;
  users: { userId: number; name: string }[];
  totalSeconds: number;
  entryCount: number;
  cardCount: number;
  peopleCount: number;
  dayCount: number;
  byUser: HoursUserRow[];
  entries: HoursEntry[];
  truncated: boolean;
  disclaimer: string;
}

export const getHours = (boardId: number, query: HoursQuery) => api<Hours>(`/api/v1/boards/${boardId}/hours`, { query });
