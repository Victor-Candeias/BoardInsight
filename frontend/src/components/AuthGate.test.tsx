import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api/client";
import { AuthGate, UserMenu } from "@/components/AuthGate";
import { mockFetch, renderWithProviders } from "@/test/utils";

const ana = { username: "ana.silva@w2k.ctt.pt", name: "Ana Silva", email: "ana.silva@ctt.pt" };

function renderGate() {
  return renderWithProviders(
    <AuthGate>
      <UserMenu />
      <p>conteúdo protegido</p>
    </AuthGate>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("AuthGate", () => {
  it("mostra a app sem login quando a autenticação está desligada", async () => {
    mockFetch({ "GET /api/v1/auth/me": () => ({ authEnabled: false, user: null }) });
    renderGate();
    expect(await screen.findByText("conteúdo protegido")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /terminar sessão/i })).not.toBeInTheDocument();
  });

  it("pede login sem sessão, mostra o erro do domínio e entra com credenciais válidas", async () => {
    const fetch = mockFetch({
      "GET /api/v1/auth/me": () => [401, { error: { code: "unauthenticated", message: "sessão inexistente" } }],
      "POST /api/v1/auth/login": (_url, init) => {
        const body = JSON.parse(String(init?.body));
        return body.password === "certa"
          ? { authEnabled: true, user: ana }
          : [401, { error: { code: "invalid_credentials", message: "credenciais inválidas" } }];
      },
    });
    renderGate();
    const email = await screen.findByLabelText("Email");
    const password = screen.getByLabelText("Password");
    expect(screen.queryByText("conteúdo protegido")).not.toBeInTheDocument();

    fireEvent.change(email, { target: { value: " ana.silva@ctt.pt " } });
    fireEvent.change(password, { target: { value: "errada" } });
    fireEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("credenciais inválidas");
    expect(password).toHaveValue("");

    fireEvent.change(password, { target: { value: "certa" } });
    fireEvent.click(screen.getByRole("button", { name: /entrar/i }));
    expect(await screen.findByText("conteúdo protegido")).toBeInTheDocument();
    expect(screen.getByText("Ana Silva")).toBeInTheDocument();
    const loginCall = fetch.mock.calls.filter(([url]) => url === "/api/v1/auth/login").at(-1);
    expect(JSON.parse(String(loginCall?.[1]?.body))).toEqual({ email: "ana.silva@ctt.pt", password: "certa" });
  });

  it("volta ao login quando a sessão expira ou é terminada", async () => {
    mockFetch({
      "GET /api/v1/auth/me": () => ({ authEnabled: true, user: ana }),
      "GET /api/v1/boards": () => [401, { error: { code: "unauthenticated", message: "sessão expirada" } }],
      "POST /api/v1/auth/logout": () => [204, null],
    });
    const { unmount } = renderGate();
    expect(await screen.findByText("conteúdo protegido")).toBeInTheDocument();
    await expect(api("/api/v1/boards")).rejects.toThrow("sessão expirada");
    expect(await screen.findByLabelText("Email")).toBeInTheDocument();
    unmount();

    renderGate();
    fireEvent.click(await screen.findByRole("button", { name: /terminar sessão/i }));
    await waitFor(() => expect(screen.getByLabelText("Email")).toBeInTheDocument());
  });
});
