import { api } from "@/api/client";

export interface BoardSummary {
  boardId: number;
  name: string;
  workspaceId: number | null;
  enabled: boolean;
  isArchived: boolean;
  lastSyncAt: string | null;
  lastSuccessfulSyncAt: string | null;
  lastSyncStatus: "success" | "error" | null;
  cardCount: number | null;
  createdAt: string;
  stale: boolean;
}

export interface ColumnMapping {
  columnId: number;
  name: string | null;
  parentName: string | null;
  workflowId: number | null;
  workflowName: string | null;
  section: number | null;
  sectionName: string;
  status: string;
  statusLabel: string;
  cycleTime: boolean;
  wipLimit: number | null;
  position: number | null;
}

export interface BoardDetail extends BoardSummary {
  lastSyncError: { code: string; message: string } | null;
  workflows: { workflowId: number; name: string | null; type: number | null }[];
  lanes: { laneId: number; workflowId: number | null; name: string | null; position: number | null }[];
  columns: ColumnMapping[];
  cardTypes: { typeId: number; name: string; color: string | null }[];
  metadataWarnings: string[];
}

export interface ConnectionCheck {
  name: string;
  label: string;
  ok: boolean;
  required: boolean;
  code?: string;
  message?: string;
}

export interface ConnectionResult {
  boardId: number;
  boardName: string | null;
  ok: boolean;
  checks: ConnectionCheck[];
  rateLimit: { perMinuteRemaining: number | null; perHourRemaining: number | null };
}

export interface SyncRun {
  id: string;
  boardId: number;
  trigger: "timer" | "manual";
  status: "running" | "success" | "error";
  startedAt: string;
  finishedAt?: string;
  durationMs?: number;
  stats?: Record<string, unknown>;
  error?: { code: string; message: string } | null;
}

export const boardsKey = ["boards"] as const;

export const listBoards = (search?: string) => api<BoardSummary[]>("/api/v1/boards", { query: { search } });
export const getBoard = (id: number) => api<BoardDetail>(`/api/v1/boards/${id}`);
export const addBoard = (boardId: number) =>
  api<BoardDetail>("/api/v1/boards", { method: "POST", body: JSON.stringify({ boardId }) });
export const updateBoard = (id: number, changes: { enabled?: boolean }) =>
  api<BoardDetail>(`/api/v1/boards/${id}`, { method: "PATCH", body: JSON.stringify(changes) });
export const deleteBoard = (id: number) => api<void>(`/api/v1/boards/${id}`, { method: "DELETE" });
export const testConnection = (id: number) =>
  api<ConnectionResult>(`/api/v1/boards/${id}/test-connection`, { method: "POST" });
export const listSyncRuns = (id: number) => api<SyncRun[]>(`/api/v1/boards/${id}/sync-runs`);
