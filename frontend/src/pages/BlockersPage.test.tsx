import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const period = { from: "2026-09-01", to: "2026-10-31", granularity: "month" };
const series = [
  { bucket: "2026-09-01", label: "set 2026" },
  { bucket: "2026-10-01", label: "out 2026" },
];

let requests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/blockers": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period,
        current: {
          blocked: 1,
          openTotal: 4,
          share: 0.25,
          days: { available: true, count: 1, smallSample: true, p50: 2, p85: 2, p95: 2, mean: 2, min: 2, max: 2 },
          byReason: [{ key: "Motivo 7", label: "Motivo 7", count: 1, days: 2 }],
          byOwner: [{ key: 12, label: "Rui", count: 1, days: 2 }],
          byColumn: [{ key: 2003, label: "Doing", count: 1, days: 2 }],
          items: [
            { cardId: 5003, customId: "T-3", title: "Preso", status: "in_progress", columnName: "Doing", laneName: null, ownerUserId: 12, ownerName: "Rui", reason: "Motivo 7", comment: "Aguarda dependência externa", blockedSeconds: 172800, blockedDays: 2 },
          ],
          truncated: false,
        },
        history: {
          historySince: "2026-09-01T08:00:00Z",
          started: 1,
          resolved: 1,
          resolvedDays: { available: false, reason: "sem desbloqueios observados no período", count: 0 },
          series: series.map((s, i) => ({ ...s, started: i, resolved: 1 - i })),
        },
      };
    },
    "GET /api/v1/boards/96/quality": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period,
        historySince: "2026-09-01T08:00:00Z",
        available: true,
        reopens: 3,
        reopenedCards: 2,
        completed: 4,
        reopenRate: 0.5,
        series: series.map((s, i) => ({ ...s, reopens: i + 1 })),
        items: [{ cardId: 5006, customId: null, title: "Voltou", status: "todo", columnName: "Requested", ownerName: null, reopens: 2, lastReopenedAt: "2026-10-09T12:00:00Z" }],
        truncated: false,
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra bloqueios atuais, histórico observado e reaberturas", async () => {
  renderWithProviders(<App />, { route: "/blockers?ownerUserId=12" });
  expect(await screen.findByRole("link", { name: "Bloqueados agora: 1" })).toHaveAttribute("href", "/cards?blocked=true");
  expect(screen.getByText("25% de 4 em aberto")).toBeInTheDocument();
  expect(screen.getByText("sem desbloqueios observados no período")).toBeInTheDocument();
  expect(screen.getByText(/recolhido desde/)).toBeInTheDocument();

  const blocked = screen.getByRole("table", { name: "Cartões bloqueados" });
  expect(within(blocked).getByRole("link", { name: "T-3" })).toHaveAttribute("href", "/cards/5003");
  expect(within(blocked).getByText("Aguarda dependência externa")).toBeInTheDocument();
  expect(within(blocked).getByText("2 d")).toBeInTheDocument();

  const reopened = screen.getByRole("table", { name: "Cartões reabertos" });
  expect(within(reopened).getByRole("link", { name: "5006" })).toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Reaberturas por intervalo" })).toHaveTextContent("out 20262");
  expect(screen.getByRole("table", { name: "Bloqueados por motivo" })).toHaveTextContent("Motivo 7");

  expect(requests.every((u) => u.searchParams.get("ownerUserId") === "12")).toBe(true);
  expect(requests.map((u) => u.pathname).sort()).toEqual(["/api/v1/boards/96/blockers", "/api/v1/boards/96/quality"]);
});
