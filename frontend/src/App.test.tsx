import { screen } from "@testing-library/react";
import { afterEach, it, expect, vi } from "vitest";
import App from "@/App";
import { mockFetch, renderWithProviders } from "@/test/utils";

afterEach(() => vi.unstubAllGlobals());

it("renderiza a navegação principal", async () => {
  mockFetch({ "GET /api/v1/boards": () => [] });
  renderWithProviders(<App />);
  expect(screen.getByRole("navigation", { name: "Navegação principal" })).toBeInTheDocument();
  expect(await screen.findByText("Nenhum board configurado")).toBeInTheDocument();
});
