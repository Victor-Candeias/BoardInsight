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

const definition = {
  id: "d1",
  boardId: 96,
  name: "Bloqueados da Ana",
  params: { title: "Bloqueios", filters: { ownerUserId: [11], blocked: false, overdue: false }, from: null, to: null, sort: "-priority" },
  filtersLabel: "Responsável: Ana; Não bloqueados",
  schedule: null,
  createdAt: "2026-10-21T09:00:00Z",
  updatedAt: "2026-10-21T09:00:00Z",
};

let exportsList: unknown[];
let definitions: unknown[];
let posted: Record<string, unknown> | null;
let savedDefinition: Record<string, unknown> | null;
let definitionExport: string | null;
let updatedDefinition: Record<string, unknown> | null;
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  exportsList = [done];
  definitions = [definition];
  posted = null;
  savedDefinition = null;
  definitionExport = null;
  updatedDefinition = null;
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [{ value: 11, label: "Ana" }] }),
    "GET /api/v1/reports/exports": () => exportsList,
    "GET /api/v1/reports": () => definitions,
    "POST /api/v1/reports": (_url, init) => {
      savedDefinition = JSON.parse(String(init?.body));
      const created = { ...definition, id: "d2", name: String(savedDefinition!.name), filtersLabel: "Sem filtros" };
      definitions = [...definitions, created];
      return [201, created];
    },
    "PUT /api/v1/reports/d1": (_url, init) => {
      updatedDefinition = JSON.parse(String(init?.body));
      const updated = { ...definition, schedule: { ...(updatedDefinition!.schedule as object), trigger: "sprint_end", since: "2026-10-21" } };
      definitions = [updated];
      return updated;
    },
    "POST /api/v1/reports/d1/export": (_url, init) => {
      definitionExport = JSON.parse(String(init?.body)).format;
      return [202, { ...done, id: "e3", status: "pending", downloadUrl: null }];
    },
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

it("guarda, aplica e gera relatórios a partir de definições", async () => {
  renderWithProviders(<App />, { route: "/reports?status=todo" });
  expect(await screen.findByText("Responsável: Ana; Não bloqueados")).toBeInTheDocument();
  expect(screen.getByText("Último mês")).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Título"), { target: { value: "Semana" } });
  fireEvent.change(screen.getByLabelText("Nome da definição"), { target: { value: "A fazer" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar definição" }));
  await waitFor(() => expect(savedDefinition).not.toBeNull());
  expect(savedDefinition).toMatchObject({ boardId: 96, name: "A fazer", params: { title: "Semana", filters: { status: "todo" } } });
  expect(await screen.findByText("A fazer")).toBeInTheDocument();

  fireEvent.click(screen.getAllByRole("button", { name: "XLSX" })[0]);
  await waitFor(() => expect(definitionExport).toBe("xlsx"));

  fireEvent.click(screen.getAllByRole("button", { name: "Aplicar" })[0]);
  await waitFor(() => expect(screen.getByLabelText("Título")).toHaveValue("Bloqueios"));
  expect(screen.getByLabelText("Responsável")).toHaveValue("11");
});

it("agenda uma definição para o fim de cada sprint", async () => {
  renderWithProviders(<App />, { route: "/reports" });
  const select = await screen.findByLabelText("Agendamento de Bloqueados da Ana");
  expect(select).toHaveValue("off");
  fireEvent.change(select, { target: { value: "both" } });
  await waitFor(() => expect(updatedDefinition).not.toBeNull());
  expect(updatedDefinition).toMatchObject({ name: "Bloqueados da Ana", schedule: { enabled: true, formats: ["pdf", "xlsx"] } });
  await waitFor(() => expect(screen.getByLabelText("Agendamento de Bloqueados da Ana")).toHaveValue("both"));
  expect(screen.getByText(/gerados pela sincronização periódica/)).toBeInTheDocument();
});
