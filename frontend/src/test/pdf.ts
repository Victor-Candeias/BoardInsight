import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { expect, vi } from "vitest";
import { exportElementToPdf } from "@/lib/exportPdf";

/**
 * Clica em "Exportar PDF" e confirma que é exportada a raiz da página (com o título `heading`)
 * com o nome `boardinsight-<page>-AAAA-MM-DD.pdf`. Requer `vi.mock("@/lib/exportPdf", ...)` no ficheiro de teste.
 */
export async function expectPageExportedToPdf(heading: string, page: string) {
  const exportPdf = vi.mocked(exportElementToPdf);
  exportPdf.mockClear();
  const button = await screen.findByRole("button", { name: "Exportar PDF" });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  await waitFor(() => expect(exportPdf).toHaveBeenCalledTimes(1));
  const [element, fileName] = exportPdf.mock.calls[0];
  expect(within(element).getByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
  expect(fileName).toMatch(new RegExp(`^boardinsight-${page}-\\d{4}-\\d{2}-\\d{2}\\.pdf$`));
}
