import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const dev = (userId: number | null, name: string, extra = {}) => ({
  userId,
  name,
  backlog: 0,
  todo: 0,
  inProgress: 0,
  open: 0,
  blocked: 0,
  overdue: 0,
  coOwnedOpen: 0,
  completed: 0,
  completedSize: 0,
  avgAgingDays: null,
  maxAgingDays: null,
  agingEstimated: false,
  completedSeries: [0, 0],
  ...extra,
});

let requests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/developers": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period: { from: "2026-09-01", to: "2026-10-31", granularity: "month" },
        buckets: [
          { bucket: "2026-09-01", label: "set 2026" },
          { bucket: "2026-10-01", label: "out 2026" },
        ],
        developers: [
          dev(11, "Ana", { todo: 1, inProgress: 2, open: 3, overdue: 1, avgAgingDays: 4.5, maxAgingDays: 9, agingEstimated: true, completed: 3, completedSeries: [1, 1] }),
          dev(null, "Sem responsável", { backlog: 1, open: 1 }),
        ],
        disclaimer: "Não são uma avaliação de desempenho individual.",
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra aviso, tabela por pessoa com ligações e gráficos", async () => {
  renderWithProviders(<App />, { route: "/developers?ownerUserId=11&typeId=42" });
  expect(await screen.findByText(/não são uma avaliação/i)).toBeInTheDocument();
  const table = screen.getByRole("table", { name: "Trabalho por pessoa" });
  const ana = within(table).getByText("Ana").closest("tr")!;
  expect(within(ana).getByRole("link", { name: "2" })).toHaveAttribute("href", "/cards?ownerUserId=11&status=in_progress");
  expect(ana).toHaveTextContent("4,5 d *");
  const unassigned = within(table).getByText("Sem responsável").closest("tr")!;
  expect(within(unassigned).getByRole("link", { name: "1" })).toHaveAttribute("href", "/cards?unassigned=true&status=backlog");
  expect(screen.getByRole("table", { name: "Concluídos por pessoa e período" })).toHaveTextContent("out 20261");
  expect(screen.getByText(/Estimado a partir/)).toBeInTheDocument();
  expect(requests[0].searchParams.get("typeId")).toBe("42");
});
