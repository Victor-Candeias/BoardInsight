import { api } from "@/api/client";
import { CARD_FILTER_KEYS, type CardQuery } from "@/api/cards";

export type ReportFormat = "pdf" | "xlsx";

type FilterValue = string | number | boolean | null | (string | number)[];

export interface ReportParams {
  title?: string | null;
  filters?: Partial<Record<(typeof CARD_FILTER_KEYS)[number], FilterValue>>;
  from?: string | null;
  to?: string | null;
  sort?: string | null;
  columns?: string[] | null;
}

export interface ReportExport {
  id: string;
  boardId: number;
  format: ReportFormat;
  title: string;
  params: ReportParams;
  status: "pending" | "running" | "done" | "error";
  createdAt: string;
  finishedAt: string | null;
  expiresAt: string;
  fileName: string | null;
  size: number | null;
  rows: number | null;
  error: { code: string; message: string } | null;
  downloadUrl: string | null;
}

/** Filtros, período e ordenação do URL atual → parâmetros do relatório. */
export function reportParamsFromQuery(query: CardQuery & { from?: string; to?: string }): ReportParams {
  const filters: ReportParams["filters"] = {};
  for (const key of CARD_FILTER_KEYS) {
    const value = query[key];
    if (value) filters[key] = value;
  }
  return { filters, from: query.from ?? null, to: query.to ?? null, sort: query.sort ?? null };
}

export const createReportExport = (body: ReportParams & { boardId: number; format: ReportFormat }) =>
  api<ReportExport>("/api/v1/reports/export", { method: "POST", body: JSON.stringify(body) });

export const listReportExports = (boardId: number) =>
  api<ReportExport[]>("/api/v1/reports/exports", { query: { boardId, limit: 20 } });

export interface ReportDefinition {
  id: string;
  boardId: number;
  name: string;
  params: ReportParams;
  filtersLabel: string;
  createdAt: string;
  updatedAt: string;
}

/** Parâmetros de uma definição → valores do URL (um valor por filtro, como na UI). */
export function queryFromReportParams(params: ReportParams): Record<string, string | null> {
  const out: Record<string, string | null> = { from: params.from ?? null, to: params.to ?? null, sort: params.sort ?? null };
  for (const key of CARD_FILTER_KEYS) {
    const raw = params.filters?.[key];
    const value = Array.isArray(raw) ? raw[0] : raw;
    // `blocked=false` é um filtro ("não bloqueados"); nas restantes flags `false` = sem filtro.
    const empty = value === undefined || value === null || value === "" || (value === false && key !== "blocked");
    out[key] = empty ? null : String(value);
  }
  if (out.state === "active") out.state = null;
  return out;
}

export const listReportDefinitions = (boardId: number) => api<ReportDefinition[]>("/api/v1/reports", { query: { boardId } });

export const createReportDefinition = (body: { boardId: number; name: string; params: ReportParams }) =>
  api<ReportDefinition>("/api/v1/reports", { method: "POST", body: JSON.stringify(body) });

export const deleteReportDefinition = (id: string) => api<void>(`/api/v1/reports/${id}`, { method: "DELETE" });

export const exportReportDefinition = (id: string, format: ReportFormat) =>
  api<ReportExport>(`/api/v1/reports/${id}/export`, { method: "POST", body: JSON.stringify({ format }) });
