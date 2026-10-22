import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

let requests: URL[];
let stale = false;

const dist = (pairs: [string, number][]) => pairs.map(([label, count], i) => ({ key: i, label, count }));

beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  stale = false;
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [{ value: 11, label: "Ana" }] }),
    "GET /api/v1/boards/96/dashboard": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        generatedAt: "2026-10-21T10:05:00Z",
        stale,
        period: { from: "2026-08-01", to: "2026-10-31", granularity: url.searchParams.get("granularity") ?? "week" },
        kpis: { total: 6, open: 4, backlog: 1, todo: 1, inProgress: 2, active: 3, done: 2, blocked: 1, overdue: 1, dueSoon: 0, unassigned: 1, createdInPeriod: 7, completedInPeriod: 3 },
        distributions: {
          status: dist([["Backlog", 1], ["Em curso", 2]]),
          column: dist([["Em análise", 2]]),
          lane: [],
          type: [],
          priority: [],
          owner: dist([["Ana", 2], ["Sem responsável", 1]]),
        },
        timeline: [{ bucket: "2026-09-01", label: "set 2026", created: 6, completed: 1 }],
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra KPIs com ligação à lista de cartões e gráficos com tabela acessível", async () => {
  renderWithProviders(<App />, { route: "/dashboard?ownerUserId=11" });
  const overdue = await screen.findByRole("link", { name: "Em atraso: 1" });
  expect(overdue).toHaveAttribute("href", "/cards?ownerUserId=11&overdue=true");
  expect(screen.getByRole("link", { name: "Cartões ativos: 4" })).toHaveAttribute("href", "/cards?ownerUserId=11&open=true");
  expect(screen.getByRole("link", { name: "Concluídos no período: 3" })).toHaveAttribute(
    "href",
    "/cards?ownerUserId=11&state=all&endedFrom=2026-08-01&endedTo=2026-10-31",
  );
  expect(screen.getByRole("table", { name: "Criados vs. concluídos" })).toHaveTextContent("set 2026" + "6" + "1");
  expect(screen.getByRole("table", { name: "Por responsável" })).toHaveTextContent("Sem responsável1");
  expect(screen.getAllByText("Sem dados para os filtros escolhidos.")).toHaveLength(3);
  expect(requests[0].searchParams.get("ownerUserId")).toBe("11");
});

it("envia período e granularidade e avisa quando os dados estão desatualizados", async () => {
  stale = true;
  renderWithProviders(<App />, { route: "/dashboard" });
  expect(await screen.findByText(/podem estar desatualizados/)).toBeInTheDocument();
  expect(screen.getByLabelText("De")).toHaveValue("2026-08-01");
  fireEvent.change(screen.getByLabelText("Agrupar por"), { target: { value: "month" } });
  await waitFor(() => expect(requests[requests.length - 1].searchParams.get("granularity")).toBe("month"));
  fireEvent.change(screen.getByLabelText("De"), { target: { value: "2026-09-01" } });
  await waitFor(() => expect(requests[requests.length - 1].searchParams.get("from")).toBe("2026-09-01"));
});
