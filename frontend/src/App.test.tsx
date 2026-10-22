import { fireEvent, screen } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import App from "@/App";
import { THEME_KEY } from "@/lib/theme";
import { mockFetch, renderWithProviders } from "@/test/utils";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

it("renderiza a navegação principal", async () => {
  mockFetch({ "GET /api/v1/boards": () => [] });
  renderWithProviders(<App />);
  expect(screen.getByRole("navigation", { name: "Navegação principal" })).toBeInTheDocument();
  expect(await screen.findByText("Nenhum board configurado")).toBeInTheDocument();
});

it("alterna o modo escuro e guarda a escolha para a próxima abertura", async () => {
  mockFetch({ "GET /api/v1/boards": () => [] });
  const { unmount } = renderWithProviders(<App />);
  fireEvent.click(screen.getByRole("button", { name: "Mudar para modo escuro" }));
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  unmount();

  renderWithProviders(<App />);
  fireEvent.click(await screen.findByRole("button", { name: "Mudar para modo claro" }));
  expect(document.documentElement).not.toHaveClass("dark");
  expect(localStorage.getItem(THEME_KEY)).toBe("light");
});
