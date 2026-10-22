import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { createReportExport, listReportExports, reportParamsFromQuery, type ReportExport, type ReportFormat } from "@/api/reports";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDateTime, formatNumber } from "@/lib/format";

const EXTRA_KEYS = ["from", "to", "sort"];
const POLL_MS = 2000;

const STATUS: Record<ReportExport["status"], { label: string; variant: "default" | "info" | "success" | "danger" }> = {
  pending: { label: "Em fila", variant: "default" },
  running: { label: "A gerar", variant: "info" },
  done: { label: "Pronto", variant: "success" },
  error: { label: "Erro", variant: "danger" },
};

function formatSize(bytes: number | null): string {
  if (bytes === null) return "—";
  return bytes < 1024 * 1024 ? `${formatNumber(bytes / 1024, 1)} KB` : `${formatNumber(bytes / 1024 / 1024, 1)} MB`;
}

export function ReportsPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const [title, setTitle] = useState("");
  const queryClient = useQueryClient();

  const exports = useQuery({
    queryKey: ["report-exports", boardId],
    queryFn: () => listReportExports(boardId!),
    enabled: boardId !== null,
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === "pending" || e.status === "running") ? POLL_MS : false),
  });

  const create = useMutation({
    mutationFn: (format: ReportFormat) =>
      createReportExport({ boardId: boardId!, format, title: title.trim() || null, ...reportParamsFromQuery(query) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["report-exports", boardId] }),
  });

  if (boardId === null) return <NoBoard />;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Relatórios</h1>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <p className="text-sm text-slate-600">
            Relatório geral (resumo, indicadores e lista de cartões) com os filtros abaixo. O PDF e o XLSX são gerados em segundo plano e
            ficam disponíveis para download durante o período de retenção.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="report-title">Título</Label>
              <Input id="report-title" className="w-64" placeholder="Relatório geral" maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <PeriodControls query={query} setFilter={setFilter} showGranularity={false} />
          </div>
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} />
          <div className="flex flex-wrap gap-2">
            <Button disabled={create.isPending} onClick={() => create.mutate("pdf")}>
              Gerar PDF
            </Button>
            <Button variant="outline" disabled={create.isPending} onClick={() => create.mutate("xlsx")}>
              Gerar XLSX
            </Button>
          </div>
          <ErrorAlert error={create.error} />
        </CardContent>
      </Card>

      <h2 className="text-lg font-semibold">Exportações recentes</h2>
      <ErrorAlert error={exports.error} />
      {!exports.data ? (
        !exports.error && <Loading />
      ) : exports.data.length === 0 ? (
        <p className="text-sm text-slate-500">Ainda não foram gerados relatórios para este board.</p>
      ) : (
        <Card>
          <Table>
            <THead>
              <TR>
                <TH>Pedido em</TH>
                <TH>Título</TH>
                <TH>Formato</TH>
                <TH>Estado</TH>
                <TH className="text-right">Cartões</TH>
                <TH className="text-right">Tamanho</TH>
                <TH>Expira</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {exports.data.map((e) => (
                <TR key={e.id}>
                  <TD>{formatDateTime(e.createdAt)}</TD>
                  <TD>{e.title}</TD>
                  <TD className="uppercase">{e.format}</TD>
                  <TD>
                    <Badge variant={STATUS[e.status].variant}>{STATUS[e.status].label}</Badge>
                    {e.error && <span className="ml-2 text-xs text-red-700">{e.error.message}</span>}
                  </TD>
                  <TD className="text-right">{e.rows === null ? "—" : formatNumber(e.rows)}</TD>
                  <TD className="text-right">{formatSize(e.size)}</TD>
                  <TD>{formatDateTime(e.expiresAt)}</TD>
                  <TD>
                    {e.downloadUrl && (
                      <Button asChild variant="ghost" size="sm">
                        <a href={e.downloadUrl} download aria-label={`Descarregar ${e.title} (${e.format.toUpperCase()})`}>
                          <Download className="h-4 w-4" aria-hidden="true" />
                        </a>
                      </Button>
                    )}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}
    </div>
  );
}
