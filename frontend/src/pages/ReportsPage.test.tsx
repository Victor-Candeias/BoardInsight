import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const done = {
  id: "e1",
  boardId: 96,
  format: "xlsx",
  title: "Semana 42",
  params: {},
  status: "done",
  createdAt: "2026-10-21T09:00:00Z",
  finishedAt: "2026-10-21T09:00:05Z",
  expiresAt: "2026-11-20T09:00:00Z",
  fileName: "boardinsight-board96-relatorio-20261021-1000.xlsx",
  size: 20480,
  rows: 42,
  error: null,
  downloadUrl: "/api/v1/reports/exports/e1/download",
};

let exportsList: unknown[];
let posted: Record<string, unknown> | null;
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  exportsList = [done];
  posted = null;
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/reports/exports": () => exportsList,
    "POST /api/v1/reports/export": (_url, init) => {
      posted = JSON.parse(String(init?.body));
      const created = { ...done, id: "e2", format: "pdf", title: "Relatório geral", status: "pending", size: null, rows: null, downloadUrl: null };
      exportsList = [created, done];
      return [202, created];
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("lista exportações e gera PDF com os filtros e o período do URL", async () => {
  renderWithProviders(<App />, { route: "/reports?status=done&ownerUserId=11&from=2026-09-01&to=2026-09-30&sort=-priority" });
  const link = await screen.findByRole("link", { name: "Descarregar Semana 42 (XLSX)" });
  expect(link).toHaveAttribute("href", "/api/v1/reports/exports/e1/download");
  expect(screen.getByText("Pronto")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Gerar PDF" }));
  await waitFor(() => expect(posted).not.toBeNull());
  expect(posted).toMatchObject({
    boardId: 96,
    format: "pdf",
    title: null,
    filters: { status: "done", ownerUserId: "11" },
    from: "2026-09-01",
    to: "2026-09-30",
    sort: "-priority",
  });
  expect(await screen.findByText("Em fila")).toBeInTheDocument();
});
