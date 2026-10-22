import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const base = { boardId: 96, name: "Board 96", stale: false };
const row = (id: string, name: string, extra = {}) => ({
  id,
  name,
  start: id,
  end: id,
  state: "past",
  completed: 2,
  completedSize: 9,
  commitmentAvailable: true,
  commitmentAt: "2026-09-28T08:00:00Z",
  committed: 4,
  committedDone: 2,
  completionRate: 0.5,
  ...extra,
});
const card = (cardId: number, doneInSprint = false) => ({ cardId, customId: null, title: `C${cardId}`, status: "todo", statusLabel: "A fazer", size: 1, doneInSprint });

let requests: URL[];
let config: unknown;
const sprintsResponse = (cfg: { cadence: unknown; explicit: unknown[] }) => ({
  ...base,
  dataAsOf: "2026-10-21T10:00:00Z",
  config: cfg,
  sprints: cfg.explicit.length || cfg.cadence ? [row("2026-09-28", "S1"), row("2026-10-06", "S2", { state: "current", commitmentAvailable: false, commitmentReason: "sem snapshot no primeiro dia da sprint", committed: null, committedDone: null, completionRate: null })] : [],
  upcoming: [],
  averageVelocity: 2,
  averageVelocitySprints: 1,
});

beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(96);
  requests = [];
  config = undefined;
  mockFetch({
    "GET /api/v1/boards": () => [base],
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: false, lastSuccessfulSyncAt: null, latestJob: null }),
    "GET /api/v1/boards/96/cards/filter-options": () => ({ statuses: [], priorities: [], columns: [], lanes: [], types: [], owners: [] }),
    "GET /api/v1/boards/96/sprints": () => sprintsResponse((config as never) ?? { cadence: null, explicit: [] }),
    "PUT /api/v1/boards/96/sprints/config": (_url, init) => {
      config = JSON.parse(String(init?.body));
      return config;
    },
    "GET /api/v1/boards/96/sprints/2026-09-28": (url) => {
      requests.push(url);
      return {
        ...row("2026-09-28", "S1"),
        boardId: 96,
        dataAsOf: null,
        stale: false,
        burndown: [
          { date: "2026-09-28", remaining: 4, remainingSize: 14, ideal: 4 },
          { date: "2026-09-29", remaining: null, remainingSize: null, ideal: 2 },
        ],
        commitment: [card(5002), card(5005, true)],
        added: [card(5004)],
      };
    },
    "GET /api/v1/boards/96/sprints/2026-10-06": () => ({
      ...row("2026-10-06", "S2", { commitmentAvailable: false, commitmentReason: "sem snapshot no primeiro dia da sprint", committed: null, committedDone: null, completionRate: null }),
      boardId: 96,
      dataAsOf: null,
      stale: false,
      burndown: [],
      commitment: [],
      added: [],
    }),
  });
});
afterEach(() => vi.unstubAllGlobals());

it("configura a cadência e mostra a sprint atual sem compromisso", async () => {
  renderWithProviders(<App />, { route: "/sprints" });
  fireEvent.change(await screen.findByLabelText("Definição das sprints"), { target: { value: "cadence" } });
  fireEvent.change(screen.getByLabelText("Início da 1.ª sprint"), { target: { value: "2026-09-28" } });
  fireEvent.change(screen.getByLabelText("Duração (dias)"), { target: { value: "8" } });
  fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
  await waitFor(() => expect(config).toEqual({ cadence: { start: "2026-09-28", lengthDays: 8, namePrefix: "Sprint" }, explicit: [] }));

  expect(await screen.findByText(/Compromisso e burndown indisponíveis: sem snapshot/)).toBeInTheDocument();
  expect(screen.getByLabelText("Sprint")).toHaveValue("2026-10-06");
  expect(screen.getByRole("table", { name: "Velocity por sprint" })).toHaveTextContent("S1");
});

it("mostra burndown, compromisso e âmbito adicionado da sprint escolhida", async () => {
  config = { cadence: null, explicit: [{ name: "S1", start: "2026-09-28", end: "2026-10-05" }] };
  renderWithProviders(<App />, { route: "/sprints?sprint=2026-09-28&ownerUserId=12" });
  const burndown = await screen.findByRole("table", { name: "Burndown — S1" });
  expect(within(burndown).getByText("sem snapshot")).toBeInTheDocument();
  expect(screen.getByText("Cumprimento (%)").parentElement).toHaveTextContent("Cumprimento (%)50");
  const commitment = screen.getByRole("table", { name: "Compromisso da sprint" });
  expect(within(commitment).getAllByText("Concluído na sprint")).toHaveLength(1);
  expect(within(screen.getByRole("table", { name: "Adicionados durante a sprint" })).getByRole("link", { name: "5004" })).toBeInTheDocument();
  expect(requests[0].searchParams.get("ownerUserId")).toBe("12");
  expect(requests[0].searchParams.has("sprint")).toBe(false);
});
