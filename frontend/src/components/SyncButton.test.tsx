import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { SyncButton } from "@/components/SyncButton";

const status = {
  boardId: 96,
  lastSyncAt: "2026-10-21T10:00:00Z",
  lastSuccessfulSyncAt: "2026-10-21T10:00:00Z",
  lastSyncStatus: "success",
  lastSyncError: null,
  stale: false,
  staleAfterMinutes: 90,
  running: false,
  latestJob: null,
};

const job = (s: string, extra = {}) => ({ id: "j1", type: "sync_board", status: s, payload: { boardId: 96 }, error: null, ...extra });

function json(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function renderButton() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SyncButton boardId={96} />
    </QueryClientProvider>,
  );
}

let jobStates: unknown[];
beforeEach(() => {
  jobStates = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/sync-status")) return json(status);
      if (url.endsWith("/sync") && init?.method === "POST") return json({ job: job("pending"), created: true }, 202);
      if (url.includes("/jobs/")) return json(jobStates.shift() ?? job("done"));
      return json({}, 404);
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

it("mostra a hora da última sincronização em pt-PT", async () => {
  renderButton();
  expect(await screen.findByText(/Atualizado: 21\/10\/2026, 11:00/)).toBeInTheDocument();
});

it("enfileira a sincronização e acompanha o job até terminar", async () => {
  jobStates = [job("running")];
  renderButton();
  fireEvent.click(await screen.findByRole("button", { name: "Atualizar" }));
  expect(await screen.findByRole("button", { name: "A atualizar…" })).toBeDisabled();
  await waitFor(() => expect(screen.getByRole("button", { name: "Atualizar" })).toBeEnabled(), { timeout: 5000 });
  const calls = (fetch as unknown as { mock: { calls: [string][] } }).mock.calls.map((c) => c[0]);
  expect(calls.filter((u) => u.includes("/jobs/j1")).length).toBeGreaterThanOrEqual(2);
});

it("mostra o erro quando o job falha", async () => {
  jobStates = [job("error", { error: { code: "unavailable", message: "Businessmap indisponível" } })];
  renderButton();
  fireEvent.click(await screen.findByRole("button", { name: "Atualizar" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Businessmap indisponível");
  await act(async () => {});
});
