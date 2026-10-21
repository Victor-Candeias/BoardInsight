import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import App from "@/App";
import { setActiveBoardId } from "@/hooks/useActiveBoard";
import { mockFetch, renderWithProviders } from "@/test/utils";

const board = (id: number, extra = {}) => ({
  boardId: id,
  name: `Board ${id} nome`,
  workspaceId: 35,
  enabled: true,
  isArchived: false,
  lastSyncAt: null,
  lastSuccessfulSyncAt: null,
  lastSyncStatus: null,
  cardCount: null,
  createdAt: "2026-10-21T10:00:00Z",
  stale: true,
  ...extra,
});

let boards: ReturnType<typeof board>[];
beforeEach(() => {
  localStorage.clear();
  setActiveBoardId(null);
  boards = [];
  mockFetch({
    "GET /api/v1/boards": () => boards,
    "POST /api/v1/boards": (_, init) => {
      const { boardId } = JSON.parse(String(init?.body));
      if (boardId === 404) return [404, { error: { code: "businessmap_not_found", message: "Board inexistente" } }];
      boards.push(board(boardId));
      return [201, { ...board(boardId), columns: [], lanes: [], workflows: [], cardTypes: [], metadataWarnings: [] }];
    },
    "POST /api/v1/boards/96/test-connection": () => ({
      boardId: 96,
      boardName: "Board 96 nome",
      ok: true,
      checks: [
        { name: "board", label: "Metadados do board", ok: true, required: true },
        { name: "users", label: "Utilizadores", ok: false, required: false, code: "permission_denied", message: "sem permissão" },
      ],
      rateLimit: { perMinuteRemaining: 29, perHourRemaining: 599 },
    }),
    "GET /api/v1/boards/96/sync-status": () => ({ boardId: 96, stale: true, lastSuccessfulSyncAt: null, latestJob: null }),
  });
});
afterEach(() => vi.unstubAllGlobals());

it("testa a ligação e adiciona um board, tornando-o o board ativo", async () => {
  renderWithProviders(<App />, { route: "/boards" });
  expect(await screen.findByText("Nenhum board encontrado.")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("ID do board"), { target: { value: "96" } });
  fireEvent.click(screen.getByRole("button", { name: "Testar ligação" }));
  expect(await screen.findByText(/Ligação OK — Board 96 nome/)).toBeInTheDocument();
  expect(screen.getByText(/sem permissão/)).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));
  expect(await screen.findByRole("link", { name: "Board 96 nome" })).toBeInTheDocument();
  expect(screen.getByText("Board ativo")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByLabelText("Board ativo")).toHaveValue("96"));
  expect(localStorage.getItem("boardinsight.activeBoardId")).toBe("96");
});

it("mostra o erro da API quando o board não existe", async () => {
  renderWithProviders(<App />, { route: "/boards" });
  fireEvent.change(await screen.findByLabelText("ID do board"), { target: { value: "404" } });
  fireEvent.click(screen.getByRole("button", { name: "Adicionar" }));
  expect(await screen.findByText("Board inexistente")).toBeInTheDocument();
});

it("o seletor escolhe o primeiro board quando o ativo deixou de existir", async () => {
  boards = [board(96), board(120)];
  setActiveBoardId(5);
  renderWithProviders(<App />);
  await waitFor(() => expect(screen.getByLabelText("Board ativo")).toHaveValue("96"));
  fireEvent.change(screen.getByLabelText("Board ativo"), { target: { value: "120" } });
  expect(localStorage.getItem("boardinsight.activeBoardId")).toBe("120");
});
