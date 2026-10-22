import type { ReactElement } from "react";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

type Handler = (url: URL, init?: RequestInit) => unknown | [number, unknown];

/** Substitui `fetch` por um router simples: chave "MÉTODO /caminho" → handler. Sem rota de `/auth/me`, a autenticação está desligada. */
export function mockFetch(routes: Record<string, Handler>) {
  routes = { "GET /api/v1/auth/me": () => ({ authEnabled: false, user: null }), ...routes };
  const fn = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    const handler = routes[`${init?.method ?? "GET"} ${url.pathname}`];
    if (!handler) return new Response(JSON.stringify({ error: { code: "not_found", message: "não simulado" } }), { status: 404 });
    const out = handler(url, init);
    const [status, body] = Array.isArray(out) && typeof out[0] === "number" ? (out as [number, unknown]) : [200, out];
    return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
