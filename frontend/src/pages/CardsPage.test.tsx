import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const card = (id: number, extra = {}) => ({
  boardId: 96,
  cardId: id,
  customId: `T-${id}`,
  title: `Cartão ${id}`,
  url: `https://bm/ctrl_board/96/cards/${id}/details/`,
  state: "active",
  status: "in_progress",
  statusLabel: "Em curso",
  columnName: "Em curso",
  laneName: "Equipa",
  ownerName: "Ana",
  coOwnerNames: [],
  typeName: "Bug",
  priority: 1,
  priorityLabel: "Crítica",
  size: 3,
  deadline: null,
  createdAt: "2026-09-01T10:00:00Z",
  lastModified: "2026-10-01T10:00:00Z",
  isBlocked: false,
  overdue: false,
  dueSoon: false,
  missing: false,
  ...extra,
});

let cardRequests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  cardRequests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards": (url) => {
      cardRequests.push(url);
      const page = Number(url.searchParams.get("page") ?? 1);
      return {
        items: page === 1 ? [card(1, { isBlocked: true }), card(2)] : [card(3)],
        total: 60,
        page,
        pageSize: 50,
        dataAsOf: "2026-10-21T10:00:00Z",
      };
    },
    "GET /api/v1/boards/96/cards/filter-options": () => ({
      statuses: [{ value: "done", label: "Concluído" }],
      priorities: [{ value: 1, label: "Crítica" }],
      columns: [],
      lanes: [],
      types: [],
      owners: [{ value: 11, label: "Ana" }],
    }),
    "GET /api/v1/boards/96/cards/1": () => ({
      ...card(1),
      transitions: [{ column_id: 2003, lane_id: 3001, start: "2026-09-01T10:00:00Z", end: "2026-09-03T10:00:00Z", columnName: "Em curso", laneName: "Equipa" }],
      events: [
        { occurredAt: "2026-10-02T10:00:00Z", type: "field_change", field: "status", fieldLabel: "Estado", from: "todo", to: "in_progress", fromLabel: "A fazer", toLabel: "Em curso" },
      ],
      eventsSince: "2026-10-01T10:00:00Z",
      dataAsOf: "2026-10-21T10:00:00Z",
    }),
  });
});
afterEach(() => vi.unstubAllGlobals());

const lastRequest = () => cardRequests[cardRequests.length - 1].searchParams;

it("lista cartões com estado, prioridade e indicadores", async () => {
  renderWithProviders(<App />, { route: "/cards" });
  const row = (await screen.findByRole("link", { name: "T-1" })).closest("tr")!;
  expect(within(row).getByText("Bloqueado")).toBeInTheDocument();
  expect(within(row).getByText("Crítica")).toBeInTheDocument();
  expect(screen.getByText(/60 cartões/)).toBeInTheDocument();
  expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();
});

it("aplica filtros, ordenação e paginação na API", async () => {
  renderWithProviders(<App />, { route: "/cards" });
  await screen.findByRole("link", { name: "T-1" });
  expect(lastRequest().get("sort")).toBeNull();

  fireEvent.change(screen.getByLabelText("Estado"), { target: { value: "done" } });
  await waitFor(() => expect(lastRequest().get("status")).toBe("done"));

  fireEvent.change(screen.getByLabelText("Responsável"), { target: { value: "none" } });
  await waitFor(() => expect(lastRequest().get("unassigned")).toBe("true"));
  expect(lastRequest().get("status")).toBe("done");

  fireEvent.click(screen.getByRole("button", { name: "Prioridade" }));
  await waitFor(() => expect(lastRequest().get("sort")).toBe("-priority"));
  fireEvent.click(screen.getByRole("button", { name: /Prioridade/ }));
  await waitFor(() => expect(lastRequest().get("sort")).toBe("priority"));

  fireEvent.click(screen.getByRole("button", { name: "Seguinte" }));
  await waitFor(() => expect(lastRequest().get("page")).toBe("2"));
  expect(await screen.findByRole("link", { name: "T-3" })).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Pesquisa"), { target: { value: "login" } });
  await waitFor(() => expect(lastRequest().get("q")).toBe("login"));
  expect(lastRequest().get("page")).toBeNull();
});

it("exporta CSV e JSON com os filtros atuais e sem paginação", async () => {
  renderWithProviders(<App />, { route: "/cards?status=done&sort=-priority&page=2" });
  const csv = await screen.findByRole("link", { name: "Exportar CSV" });
  const csvUrl = new URL(csv.getAttribute("href")!, "http://x");
  expect(csvUrl.pathname).toBe("/api/v1/boards/96/cards/export");
  expect(csvUrl.searchParams.get("format")).toBe("csv");
  expect(csvUrl.searchParams.get("status")).toBe("done");
  expect(csvUrl.searchParams.get("sort")).toBe("-priority");
  expect(csvUrl.searchParams.get("page")).toBeNull();
  const json = screen.getByRole("link", { name: "Exportar JSON" });
  expect(new URL(json.getAttribute("href")!, "http://x").searchParams.get("format")).toBe("json");
});

it("mostra o detalhe do cartão com o percurso no board", async () => {
  renderWithProviders(<App />, { route: "/cards/1" });
  expect(await screen.findByRole("heading", { name: "Cartão 1" })).toBeInTheDocument();
  expect(screen.getByText("2 d")).toBeInTheDocument();
  const events = screen.getByRole("table", { name: "Alterações observadas" });
  expect(events).toHaveTextContent("EstadoA fazerEm curso");
  expect(screen.getByText(/recolhidas desde 01\/10\/2026/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Abrir no Businessmap/ })).toHaveAttribute("href", expect.stringContaining("/cards/1/details/"));
});
