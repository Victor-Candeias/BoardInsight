import { fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { expectPageExportedToPdf } from "@/test/pdf";
import { mockFetch, renderWithProviders } from "@/test/utils";

vi.mock("@/lib/exportPdf", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/exportPdf")>()),
  exportElementToPdf: vi.fn(async () => {}),
}));

const summary = { available: true, count: 3, smallSample: true, p50: 10.2, p85: 18.3, p95: 19.5, mean: 12, min: 8.1, max: 20.3 };
const flow = {
  boardId: 96,
  dataAsOf: "2026-10-21T10:00:00Z",
  stale: false,
  period: { from: "2026-08-01", to: "2026-10-31", granularity: "month" },
  wip: { total: 2, blocked: 1, byColumn: [{ key: 2003, label: "Doing", count: 2 }], byLane: [], byOwner: [{ key: 11, label: "Ana", count: 2 }] },
  aging: {
    ...summary,
    count: 2,
    threshold: 18.3,
    aboveThreshold: 1,
    estimatedCount: 0,
    items: [
      { cardId: 5003, customId: "T-3", title: "Velho", columnName: "Doing", ownerName: "Ana", isBlocked: true, ageDays: 31, estimated: false, aboveP85: true },
      { cardId: 5004, customId: null, title: "Novo", columnName: "Doing", ownerName: null, isBlocked: false, ageDays: 2, estimated: true, aboveP85: false },
    ],
  },
  leadTime: { available: false, reason: "sem cartões concluídos no período", count: 0 },
  cycleTime: { ...summary, withoutStart: 1 },
  trend: [{ bucket: "2026-09-01", label: "set 2026", count: 1, cycleP50: 8.1, cycleP85: 8.1, leadP50: 10 }],
  points: [{ cardId: 5006, customId: null, title: "Feito", typeName: null, endTime: "2026-09-30T12:00:00Z", leadDays: 10.2, cycleDays: 8.1 }],
};

let requests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/flow": (url) => {
      requests.push(url);
      return flow;
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra percentis, métricas indisponíveis, aging acima do P85 e dispersão", async () => {
  renderWithProviders(<App />, { route: "/flow?from=2026-08-01&to=2026-10-31&ownerUserId=11" });
  expect(await screen.findByRole("link", { name: "WIP (em curso): 2" })).toBeInTheDocument();
  expect(screen.getByText("3 cartões · amostra pequena")).toBeInTheDocument();
  expect(screen.getByText(/1 concluídos sem data de início/)).toBeInTheDocument();

  const pct = screen.getByRole("table", { name: "Percentis" });
  expect(within(pct).getByText("Indisponível: sem cartões concluídos no período")).toBeInTheDocument();
  expect(within(pct).getAllByText("18,3 d")).toHaveLength(2);

  const aging = screen.getByRole("table", { name: "Aging do WIP" });
  expect(within(aging).getByRole("link", { name: "T-3" })).toHaveAttribute("href", "/cards/5003");
  expect(within(aging).getAllByText("Acima do P85")).toHaveLength(1);
  expect(within(aging).getAllByRole("row")[2]).toHaveTextContent("2 d *");

  const scatter = screen.getByRole("table", { name: "Cycle time por cartão concluído (dias)" });
  expect(within(scatter).getByText("8,1")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Dispersão"), { target: { value: "leadDays" } });
  expect(screen.getByRole("table", { name: "Lead time por cartão concluído (dias)" })).toBeInTheDocument();

  expect(requests[0].searchParams.get("ownerUserId")).toBe("11");
  expect(requests[0].searchParams.get("from")).toBe("2026-08-01");
});

it("exporta a página Fluxo para PDF tal como aparece", async () => {
  renderWithProviders(<App />, { route: "/flow" });
  await screen.findByRole("link", { name: "WIP (em curso): 2" });
  await expectPageExportedToPdf("Fluxo", "fluxo");
});
