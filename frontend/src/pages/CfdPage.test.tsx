import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

let requests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/cfd": (url) => {
      requests.push(url);
      const byColumn = url.searchParams.get("group") === "column";
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period: { from: "2026-10-01", to: "2026-10-02", granularity: "day" },
        group: byColumn ? "column" : "status",
        filtered: url.searchParams.has("ownerUserId"),
        snapshotsSince: "2026-10-01T08:00:00Z",
        available: true,
        series: byColumn
          ? [{ key: "2001", label: "Requested" }, { key: "2003", label: "Doing" }]
          : [{ key: "backlog", label: "Backlog" }, { key: "done", label: "Concluído" }],
        days: [
          { date: "2026-10-01", capturedAt: "2026-10-01T18:00:00Z", counts: byColumn ? { "2001": 2, "2003": 1 } : { backlog: 3, done: 1 } },
          { date: "2026-10-02", capturedAt: "2026-10-02T18:00:00Z", counts: byColumn ? { "2001": 1, "2003": 2 } : { backlog: 2, done: 2 } },
        ],
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra o CFD por estado e muda para colunas", async () => {
  renderWithProviders(<App />, { route: "/cfd?ownerUserId=11" });
  const table = await screen.findByRole("table", { name: "Cumulative Flow Diagram por estado" });
  expect(within(table).getAllByRole("row")[1]).toHaveTextContent("01/10/2026" + "31");
  expect(screen.getByText(/Histórico recolhido desde/)).toBeInTheDocument();
  expect(screen.getByText(/atributos atuais dos cartões/)).toBeInTheDocument();
  expect(screen.queryByLabelText("Agrupar por")).not.toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("Séries"), { target: { value: "column" } });
  const byColumn = await screen.findByRole("table", { name: "Cumulative Flow Diagram por coluna" });
  expect(within(byColumn).getByText("Doing")).toBeInTheDocument();
  expect(requests.at(-1)!.searchParams.get("group")).toBe("column");
  expect(requests.at(-1)!.searchParams.get("ownerUserId")).toBe("11");
});
