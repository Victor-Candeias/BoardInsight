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
 * são divididas em várias páginas PDF. Elementos com `data-pdf-exclude` não são incluídos e os
 * contentores com scroll são capturados por inteiro, sem barras de scroll (`expandForPdfCapture`).
 */
export async function exportElementToPdf(element: HTMLElement, fileName: string) {
  // Carregados a pedido: só são precisos quando se exporta.
  const [{ toCanvas }, { jsPDF }] = await Promise.all([import("html-to-image"), import("jspdf")]);
  const background = getComputedStyle(document.body).backgroundColor;

  const restore = expandForPdfCapture(element);
  let capture: HTMLCanvasElement;
  try {
    await nextFrame();
    capture = await toCanvas(element, {
      pixelRatio: PIXEL_RATIO,
      backgroundColor: background,
      skipFonts: true,
      filter: (node) => !(node instanceof Element && node.hasAttribute(PDF_EXCLUDE_ATTR)),
    });
  } finally {
    restore();
  }

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

const SCROLLING = new Set(["auto", "scroll"]);
/** Tentativas de alargar a página até as tabelas largas caberem sem scroll horizontal. */
const MAX_WIDEN_STEPS = 3;

/**
 * "Modo PDF": a captura copia os estilos calculados de cada elemento, por isso os contentores com
 * scroll (ex.: tabelas em `overflow-x-auto`) sairiam com barras de scroll e conteúdo cortado.
 * Durante a captura, esses contentores mostram todo o conteúdo (`overflow: visible`, sem altura
 * máxima) e, se houver conteúdo mais largo do que o contentor, a raiz é alargada até caber.
 * Devolve a função que repõe estilos e posições de scroll (o ecrã fica como estava).
 */
export function expandForPdfCapture(root: HTMLElement): () => void {
  const saved: { el: HTMLElement; style: string | null; left: number; top: number }[] = [];
  const save = (el: HTMLElement) =>
    saved.push({ el, style: el.getAttribute("style"), left: el.scrollLeft, top: el.scrollTop });
  const windowScroll = { x: window.scrollX, y: window.scrollY };

  const containers = [root, ...root.querySelectorAll<HTMLElement>("*")].filter((el) => {
    if (!(el instanceof HTMLElement)) return false;
    const style = getComputedStyle(el);
    return SCROLLING.has(style.overflowX) || SCROLLING.has(style.overflowY);
  });
  const horizontalOverflow = () => Math.max(0, ...containers.map((el) => el.scrollWidth - el.clientWidth));

  save(root);
  let extra = horizontalOverflow();
  for (const el of containers) {
    if (el !== root) save(el);
    el.style.setProperty("overflow", "visible", "important");
    el.style.setProperty("max-height", "none", "important");
    if (el.scrollHeight > el.clientHeight + 1) el.style.setProperty("height", "auto", "important");
  }
  for (let step = 0; step < MAX_WIDEN_STEPS && extra > 1; step++) {
    root.style.setProperty("max-width", "none", "important");
    root.style.setProperty("width", `${Math.ceil(root.getBoundingClientRect().width + extra)}px`, "important");
    extra = horizontalOverflow();
  }

  return () => {
    for (const { el, style } of saved.reverse()) {
      if (style === null) el.removeAttribute("style");
      else el.setAttribute("style", style);
    }
    for (const { el, left, top } of saved) {
      el.scrollLeft = left;
      el.scrollTop = top;
    }
    if (window.scrollX !== windowScroll.x || window.scrollY !== windowScroll.y) window.scrollTo(windowScroll.x, windowScroll.y);
  };
}

/** Deixa o browser (e gráficos que reagem a mudanças de tamanho) atualizar o layout antes da captura. */
function nextFrame() {
  return new Promise<void>((resolve) => {
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    else setTimeout(resolve, 0);
  });
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
