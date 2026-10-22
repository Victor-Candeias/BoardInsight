/** 1 px CSS = 0,75 pt (96 dpi → 72 pt por polegada). */
const PX_TO_PT = 0.75;
const PIXEL_RATIO = 2;
const MARGIN_PX = 24;
/** Limite de altura de página aceite pelos leitores de PDF (200 polegadas). */
const MAX_PAGE_PT = 14400;

export const PDF_EXCLUDE_ATTR = "data-pdf-exclude";

/** Nome do ficheiro: `boardinsight-<página>-<AAAA-MM-DD>.pdf` (data local). */
export function pdfFileName(page: string, now = new Date()) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `boardinsight-${page}-${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}.pdf`;
}

/**
 * Exporta um elemento para PDF tal como aparece no ecrã (tema, filtros, gráficos e tabelas):
 * captura-o como imagem e coloca-o numa página com a mesma proporção. Páginas muito compridas
 * são divididas em várias páginas PDF. Elementos com `data-pdf-exclude` não são incluídos.
 */
export async function exportElementToPdf(element: HTMLElement, fileName: string) {
  // Carregados a pedido: só são precisos quando se exporta.
  const [{ toCanvas }, { jsPDF }] = await Promise.all([import("html-to-image"), import("jspdf")]);
  const background = getComputedStyle(document.body).backgroundColor;

  const capture = await toCanvas(element, {
    pixelRatio: PIXEL_RATIO,
    backgroundColor: background,
    skipFonts: true,
    filter: (node) => !(node instanceof Element && node.hasAttribute(PDF_EXCLUDE_ATTR)),
  });

  const margin = MARGIN_PX * PIXEL_RATIO;
  const ptPerPx = PX_TO_PT / PIXEL_RATIO;
  const pageWidthPx = capture.width + 2 * margin;
  const maxSlicePx = Math.floor((MAX_PAGE_PT / ptPerPx) - 2 * margin);

  let pdf: InstanceType<typeof jsPDF> | null = null;
  for (let top = 0; top < capture.height; top += maxSlicePx) {
    const sliceHeight = Math.min(maxSlicePx, capture.height - top);
    const page = document.createElement("canvas");
    page.width = pageWidthPx;
    page.height = sliceHeight + 2 * margin;
    const ctx = page.getContext("2d");
    if (!ctx) throw new Error("O browser não permite gerar a imagem da página.");
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, page.width, page.height);
    ctx.drawImage(capture, 0, top, capture.width, sliceHeight, margin, margin, capture.width, sliceHeight);

    const size: [number, number] = [page.width * ptPerPx, page.height * ptPerPx];
    const orientation = size[0] > size[1] ? "landscape" : "portrait";
    if (!pdf) pdf = new jsPDF({ unit: "pt", format: size, orientation, compress: true });
    else pdf.addPage(size, orientation);
    pdf.addImage(page, "PNG", 0, 0, size[0], size[1], undefined, "FAST");
  }
  if (!pdf) throw new Error("A página está vazia.");

  downloadBlob(pdf.output("blob"), fileName);
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
