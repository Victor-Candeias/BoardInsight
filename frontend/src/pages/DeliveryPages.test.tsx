import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { expectPageExportedToPdf } from "@/test/pdf";
import { mockFetch, renderWithProviders } from "@/test/utils";

vi.mock("@/lib/exportPdf", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/exportPdf")>()),
  exportElementToPdf: vi.fn(async () => {}),
}));

let requests: URL[];
const card = (id: number, days: number, extra = {}) => ({
  cardId: id,
  customId: `T-${id}`,
  title: `Cartão ${id}`,
  status: "in_progress",
  statusLabel: "Em curso",
  ownerName: "Ana",
  priority: 2,
  priorityLabel: "Alta",
  deadline: "2026-10-10T00:00:00Z",
  daysToDeadline: days,
  ...extra,
});

beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/throughput": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        period: { from: "2026-09-30", to: "2026-10-11", granularity: "week" },
        total: 2,
        totalSize: 9,
        averagePerBucket: 1,
        series: [
          { bucket: "2026-09-28", label: "2026-S40", count: 1, size: 1, partial: true },
          { bucket: "2026-10-05", label: "2026-S41", count: 1, size: 8, partial: false },
        ],
        byType: [{ key: 43, label: "Bug", count: 2 }],
      };
    },
    "GET /api/v1/boards/96/deadlines": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        dueSoonDays: 7,
        openTotal: 4,
        withoutDeadline: 1,
        overdue: { total: 1, items: [card(5002, -11.4)], truncated: false },
        dueSoon: { total: 0, items: [], truncated: false },
        overdueByOwner: [{ key: 11, label: "Ana", count: 1 }],
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("mostra throughput por intervalo, média e intervalos parciais", async () => {
  renderWithProviders(<App />, { route: "/throughput?ownerUserId=11" });
  expect(await screen.findByText("Média por semana")).toBeInTheDocument();
  const table = screen.getByRole("table", { name: /Throughput/ });
  expect(table).toHaveTextContent("2026-S4011sim");
  expect(screen.getByText(/intervalos cortados/)).toBeInTheDocument();
  expect(requests[0].searchParams.get("ownerUserId")).toBe("11");
  fireEvent.change(screen.getByLabelText("Agrupar por"), { target: { value: "day" } });
  await waitFor(() => expect(requests[requests.length - 1].searchParams.get("granularity")).toBe("day"));
});

it("exporta a página Throughput para PDF tal como aparece", async () => {
  renderWithProviders(<App />, { route: "/throughput" });
  await screen.findByText("Média por semana");
  await expectPageExportedToPdf("Throughput", "throughput");
});

it("lista cartões em atraso e a vencer com dias até ao prazo", async () => {
  renderWithProviders(<App />, { route: "/deadlines" });
  const overdue = await screen.findByRole("table", { name: "Em atraso" });
  const row = within(overdue).getByRole("link", { name: "T-5002" }).closest("tr")!;
  expect(row).toHaveTextContent("10/10/2026");
  expect(row).toHaveTextContent("-11,4 d");
  expect(within(screen.getByRole("table", { name: /A vencer/ })).getByText("Nenhum prazo nos próximos dias.")).toBeInTheDocument();
  expect(screen.getByText("de 4 cartões abertos")).toBeInTheDocument();
});

it("exporta a página Prazos para PDF tal como aparece", async () => {
  renderWithProviders(<App />, { route: "/deadlines" });
  await screen.findByRole("table", { name: "Em atraso" });
  await expectPageExportedToPdf("Prazos", "prazos");
});
