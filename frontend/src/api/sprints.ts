import { api } from "@/api/client";
import type { CardQuery } from "@/api/cards";

export interface SprintCadence {
  start: string;
  lengthDays: number;
  namePrefix?: string;
}

export interface ExplicitSprint {
  name: string;
  start: string;
  end: string;
}

export interface SprintConfig {
  cadence: SprintCadence | null;
  explicit: ExplicitSprint[];
}

export interface SprintRow {
  id: string;
  name: string;
  start: string;
  end: string;
  state: "past" | "current" | "future";
  completed: number;
  completedSize: number;
  commitmentAvailable: boolean;
  commitmentReason?: string;
  commitmentAt?: string;
  committed: number | null;
  committedDone: number | null;
  completionRate: number | null;
}

export interface SprintCardRow {
  cardId: number;
  customId: string | null;
  title: string | null;
  status: string | null;
  statusLabel: string | null;
  size: number | null;
  doneInSprint: boolean;
}

export interface SprintDetail extends SprintRow {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  burndown: { date: string; remaining: number | null; remainingSize: number | null; ideal: number }[];
  commitment: SprintCardRow[];
  added: SprintCardRow[];
  committedSize?: number;
}

export interface Sprints {
  boardId: number;
  dataAsOf: string | null;
  stale: boolean;
  config: SprintConfig;
  sprints: SprintRow[];
  upcoming: { id: string; name: string; start: string; end: string }[];
  averageVelocity: number | null;
  averageVelocitySprints: number;
}

export const getSprints = (boardId: number, query: CardQuery) => api<Sprints>(`/api/v1/boards/${boardId}/sprints`, { query });
export const getSprint = (boardId: number, sprintId: string, query: CardQuery) =>
  api<SprintDetail>(`/api/v1/boards/${boardId}/sprints/${sprintId}`, { query });
export const saveSprintConfig = (boardId: number, config: SprintConfig) =>
  api<SprintConfig>(`/api/v1/boards/${boardId}/sprints/config`, { method: "PUT", body: JSON.stringify(config) });
