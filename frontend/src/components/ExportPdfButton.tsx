import { useState, type RefObject } from "react";
import { FileDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { exportElementToPdf, pdfFileName, PDF_EXCLUDE_ATTR } from "@/lib/exportPdf";
import { cn } from "@/lib/utils";

interface Props {
  /** Elemento exportado (normalmente a raiz da página). */
  target: RefObject<HTMLElement | null>;
  /** Identificador da página no nome do ficheiro (ex.: `atencao`). */
  page: string;
  disabled?: boolean;
}

/** Botão "Exportar PDF": exporta a página tal como aparece; o próprio botão não entra no PDF. */
export function ExportPdfButton({ target, page, disabled }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function exportPdf() {
    if (!target.current) return;
    setBusy(true);
    setError(null);
    try {
      await exportElementToPdf(target.current, pdfFileName(page));
    } catch (e) {
      setError(e instanceof Error && e.message ? `Não foi possível exportar: ${e.message}` : "Não foi possível exportar o PDF.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="flex items-center gap-2 text-sm" {...{ [PDF_EXCLUDE_ATTR]: "" }}>
      {error && (
        <span role="alert" className="text-red-700">
          {error}
        </span>
      )}
      <Button size="sm" variant="outline" onClick={exportPdf} disabled={disabled || busy}>
        <FileDown className={cn("h-4 w-4", busy && "animate-pulse")} aria-hidden />
        {busy ? "A exportar…" : "Exportar PDF"}
      </Button>
    </span>
  );
}
