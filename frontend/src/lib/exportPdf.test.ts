import { afterEach, expect, test, vi } from "vitest";
import { toCanvas } from "html-to-image";
import { expandForPdfCapture, exportElementToPdf } from "./exportPdf";

vi.mock("html-to-image", () => ({ toCanvas: vi.fn() }));

function pageWithScrollingTable() {
  const root = document.createElement("div");
  root.innerHTML = `
    <div id="card" style="overflow-x: auto; max-height: 200px">
      <div id="table" style="overflow-y: auto"><table><tr><td>188523</td></tr></table></div>
    </div>`;
  document.body.appendChild(root);
  return { root, card: root.querySelector<HTMLElement>("#card")!, table: root.querySelector<HTMLElement>("#table")! };
}

function setBox(el: HTMLElement, box: { scrollWidth?: number; clientWidth?: number }) {
  for (const [key, value] of Object.entries(box)) Object.defineProperty(el, key, { configurable: true, value });
}

afterEach(() => {
  document.body.innerHTML = "";
});

test("modo PDF mostra os contentores com scroll por inteiro e repõe tudo no fim", () => {
  const { root, card, table } = pageWithScrollingTable();
  table.scrollLeft = 0;

  const restore = expandForPdfCapture(root);
  for (const el of [card, table]) {
    expect(el.style.overflow).toBe("visible");
    expect(el.style.maxHeight).toBe("none");
  }
  restore();

  expect(card.getAttribute("style")).toBe("overflow-x: auto; max-height: 200px");
  expect(table.getAttribute("style")).toBe("overflow-y: auto");
  expect(root.hasAttribute("style")).toBe(false);
});

test("modo PDF alarga a página quando uma tabela é mais larga do que o contentor", () => {
  const { root, table } = pageWithScrollingTable();
  setBox(table, { scrollWidth: 1300, clientWidth: 1000 });
  root.getBoundingClientRect = () => ({ width: 1048 }) as DOMRect;

  const restore = expandForPdfCapture(root);
  expect(root.style.width).toBe("1348px");
  expect(root.style.maxWidth).toBe("none");
  restore();
  expect(root.hasAttribute("style")).toBe(false);
});

test("exportação captura em modo PDF e repõe a página mesmo quando a captura falha", async () => {
  const { root, table } = pageWithScrollingTable();
  vi.mocked(toCanvas).mockImplementationOnce(async () => {
    expect(table.style.overflow).toBe("visible");
    throw new Error("sem memória");
  });

  await expect(exportElementToPdf(root, "x.pdf")).rejects.toThrow("sem memória");
  expect(table.getAttribute("style")).toBe("overflow-y: auto");
  expect(toCanvas).toHaveBeenCalledTimes(1);
});
