import { api } from "@/api/client";

export type JobStatus = "pending" | "running" | "done" | "error";

export interface Job {
  id: string;
  type: string;
  status: JobStatus;
  payload: Record<string, unknown>;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  result: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
}

export interface SyncStatus {
  boardId: number;
  lastSyncAt: string | null;
  lastSuccessfulSyncAt: string | null;
  lastSyncStatus: "success" | "error" | null;
  lastSyncError: { code: string; message: string } | null;
  stale: boolean;
  staleAfterMinutes: number;
  running: boolean;
  latestJob: Job | null;
}

export const syncStatusKey = (boardId: number) => ["sync-status", boardId] as const;

export const getSyncStatus = (boardId: number) => api<SyncStatus>(`/api/v1/boards/${boardId}/sync-status`);
export const enqueueSync = (boardId: number) =>
  api<{ job: Job; created: boolean }>(`/api/v1/boards/${boardId}/sync`, { method: "POST" });
export const getJob = (jobId: string) => api<Job>(`/api/v1/jobs/${jobId}`);

export const isActiveJob = (job: Job | null | undefined) => job?.status === "pending" || job?.status === "running";
