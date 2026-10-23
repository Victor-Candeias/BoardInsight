import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { formatHours } from "@/lib/format";
import { mockFetch, renderWithProviders } from "@/test/utils";

let requests: URL[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  mockFetch({
    "GET /api/v1/boards": () => [{ boardId: 96, name: "Board 96", stale: false }],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/hours": (url) => {
      requests.push(url);
      return {
        boardId: 96,
        dataAsOf: "2026-10-21T10:00:00Z",
        stale: false,
        available: true,
        warning: null,
        period: { from: "2026-10-01", to: "2026-10-31", granularity: "month" },
        buckets: [{ bucket: "2026-10-01", label: "out 2026" }],
        userId: null,
        includeSubtasks: true,
        users: [
          { userId: 11, name: "Ana" },
          { userId: 12, name: "Rui" },
        ],
        totalSeconds: 549000,
        entryCount: 2,
        cardCount: 2,
        peopleCount: 2,
        dayCount: 2,
        byUser: [
          { userId: 11, name: "Ana", seconds: 547200, entries: 1, cards: 1, days: 1, avgSecondsPerDay: 547200, series: [547200] },
          { userId: 12, name: "Rui", seconds: 1800, entries: 1, cards: 1, days: 1, avgSecondsPerDay: 1800, series: [1800] },
        ],
        entries: [
          {
            loggedTimeId: 2,
            date: "2026-10-20",
            userId: 12,
            userName: "Rui",
            cardId: 5001,
            customId: "T-5001",
            title: "Pagamentos",
            url: null,
            subtask: true,
            seconds: 1800,
            comment: "Revisão",
          },
          {
            loggedTimeId: 1,
            date: "2026-10-19",
            userId: 11,
            userName: "Ana",
            cardId: 5002,
            customId: null,
            title: null,
            url: null,
            subtask: false,
            seconds: 547200,
            comment: null,
          },
        ],
        truncated: false,
        disclaimer: "Horas registadas no Businessmap.",
      };
    },
  });
});
afterEach(() => vi.unstubAllGlobals());

it("formata horas em HH:mm, incluindo totais acima de 99 horas", () => {
  expect(formatHours(0)).toBe("00:00");
  expect(formatHours(1800)).toBe("00:30");
  expect(formatHours(549000)).toBe("152:30");
  expect(formatHours(null)).toBe("—");
});

it("mostra horas por utilizador e registos, e filtra por utilizador e subtarefas", async () => {
  renderWithProviders(<App />, { route: "/hours?from=2026-10-01&to=2026-10-31&granularity=month" });
  expect(await screen.findByText("Horas registadas no Businessmap.")).toBeInTheDocument();
  expect(screen.getByText("152:30")).toBeInTheDocument();

  const byUser = screen.getByRole("table", { name: "Horas por utilizador" });
  const ana = within(byUser).getByText("Ana").closest("tr")!;
  expect(ana).toHaveTextContent("152:00");

  const entries = screen.getByRole("table", { name: "Registos de tempo" });
  const rui = within(entries).getByText("Rui").closest("tr")!;
  expect(within(rui).getByRole("link", { name: /T-5001 · Pagamentos/ })).toHaveAttribute("href", "/cards/5001");
  expect(rui).toHaveTextContent("Subtarefa");
  expect(rui).toHaveTextContent("00:30");
  expect(within(entries).getByRole("link", { name: "#5002" })).toBeInTheDocument();

  expect(requests[0].searchParams.get("userId")).toBeNull();
  expect(requests[0].searchParams.get("includeSubtasks")).toBeNull();

  fireEvent.change(screen.getByLabelText("Utilizador"), { target: { value: "12" } });
  await waitFor(() => expect(requests.at(-1)!.searchParams.get("userId")).toBe("12"));

  fireEvent.click(screen.getByLabelText("Incluir subtarefas"));
  await waitFor(() => expect(requests.at(-1)!.searchParams.get("includeSubtasks")).toBe("false"));
  expect(requests.at(-1)!.searchParams.get("from")).toBe("2026-10-01");
});
