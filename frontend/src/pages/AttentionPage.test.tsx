import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const item = (cardId: number, reasons: string[], extra = {}) => ({
  cardId,
  customId: `C-${cardId}`,
  title: `Cartão ${cardId}`,
  status: "in_progress",
  statusLabel: "Em curso",
  columnName: "Em análise",
  ownerUserId: 11,
  ownerName: "Ana",
  reasons,
  score: 1,
  blockedDays: null,
  blockReason: null,
  ageDays: null,
  ageEstimated: false,
  deadline: null,
  daysToDeadline: null,
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
    "GET /api/v1/boards/96/attention": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period: { from: "2026-09-22", to: "2026-10-22" },
        dueSoonDays: 7,
        wipLimit: 3,
        agingReference: { p85: 18.7, count: 3, smallSample: true },
        openTotal: 10,
        summary: { blocked: 1, overdue: 1, aging: 1, dueSoon: 0, unassigned: 1, wipOverLimit: 1, reopenedCards: 2 },
        reopensAvailable: true,
        total: 3,
        items: [
          item(5003, ["blocked", "aging"], { blockedDays: 2.5, blockReason: "Dependência", ageDays: 32 }),
          item(5002, ["overdue"], { deadline: "2026-10-10T17:00:00Z", daysToDeadline: -12 }),
          item(5001, ["unassigned"], { ownerUserId: null, ownerName: null }),
        ],
        truncated: false,
        people: [{ userId: 12, name: "Bruno", inProgress: 5 }],
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("é a página inicial e o primeiro item do menu", async () => {
  renderWithProviders(<App />, { route: "/" });
  expect(await screen.findByRole("heading", { name: "Atenção" })).toBeInTheDocument();
  const nav = screen.getByRole("navigation", { name: "Navegação principal" });
  const first = within(nav).getAllByRole("link")[0];
  expect(first).toHaveTextContent("Atenção");
  expect(first).toHaveAttribute("href", "/");
  expect(within(nav).getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/dashboard");
});

it("lista cartões por urgência, filtra por motivo e mostra WIP alto", async () => {
  renderWithProviders(<App />, { route: "/?laneId=3" });
  const table = await screen.findByRole("table", { name: "Cartões que exigem ação" });
  expect(within(table).getAllByRole("row")).toHaveLength(4);
  expect(within(table).getByText(/bloqueado há 2,5 d \(Dependência\)/)).toBeInTheDocument();
  expect(within(table).getByRole("link", { name: "C-5003" })).toHaveAttribute("href", "/cards/5003");

  fireEvent.click(screen.getByRole("button", { name: "Em atraso: 1" }));
  expect(within(table).getAllByRole("row")).toHaveLength(2);
  expect(within(table).getByText("Cartão 5002")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Em atraso: 1" })).toHaveAttribute("aria-pressed", "true");

  const wip = screen.getByRole("list", { name: "WIP alto por pessoa" });
  expect(within(wip).getByRole("link", { name: "5 em curso" })).toHaveAttribute("href", "/cards?ownerUserId=12&status=in_progress");
  expect(requests[0].searchParams.get("laneId")).toBe("3");
});
