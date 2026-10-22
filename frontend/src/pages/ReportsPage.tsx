import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Trash2 } from "lucide-react";
import {
  createReportDefinition,
  createReportExport,
  deleteReportDefinition,
  exportReportDefinition,
  listReportDefinitions,
  listReportExports,
  queryFromReportParams,
  reportParamsFromQuery,
  type ReportDefinition,
  type ReportExport,
  type ReportFormat,
} from "@/api/reports";
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
  const [name, setName] = useState("");
  const queryClient = useQueryClient();
  const refreshExports = () => queryClient.invalidateQueries({ queryKey: ["report-exports", boardId] });
  const refreshDefinitions = () => queryClient.invalidateQueries({ queryKey: ["report-definitions", boardId] });

  const definitions = useQuery({
    queryKey: ["report-definitions", boardId],
    queryFn: () => listReportDefinitions(boardId!),
    enabled: boardId !== null,
  });

  const exports = useQuery({
    queryKey: ["report-exports", boardId],
    queryFn: () => listReportExports(boardId!),
    enabled: boardId !== null,
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === "pending" || e.status === "running") ? POLL_MS : false),
  });

  const create = useMutation({
    mutationFn: (format: ReportFormat) =>
      createReportExport({ boardId: boardId!, format, title: title.trim() || null, ...reportParamsFromQuery(query) }),
    onSuccess: refreshExports,
  });
  const save = useMutation({
    mutationFn: () =>
      createReportDefinition({ boardId: boardId!, name: name.trim(), params: { ...reportParamsFromQuery(query), title: title.trim() || null } }),
    onSuccess: () => {
      setName("");
      return refreshDefinitions();
    },
  });
  const generate = useMutation({
    mutationFn: ({ id, format }: { id: string; format: ReportFormat }) => exportReportDefinition(id, format),
    onSuccess: refreshExports,
  });
  const remove = useMutation({ mutationFn: deleteReportDefinition, onSuccess: refreshDefinitions });

  const apply = (d: ReportDefinition) => {
    setFilters(queryFromReportParams(d.params));
    setTitle(d.params.title ?? "");
  };

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
          <form
            className="flex flex-wrap items-end gap-2 border-t pt-3"
            onSubmit={(e) => {
              e.preventDefault();
              save.mutate();
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="definition-name">Nome da definição</Label>
              <Input id="definition-name" className="w-64" maxLength={80} required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <Button type="submit" variant="outline" disabled={save.isPending || !name.trim()}>
              Guardar definição
            </Button>
          </form>
          <ErrorAlert error={save.error} />
        </CardContent>
      </Card>

      <h2 className="text-lg font-semibold">Definições guardadas</h2>
      <ErrorAlert error={definitions.error ?? generate.error ?? remove.error} />
      {definitions.data && definitions.data.length === 0 && (
        <p className="text-sm text-slate-500">Sem definições. Escolha os filtros acima e guarde-os com um nome para reutilizar.</p>
      )}
      {definitions.data && definitions.data.length > 0 && (
        <Card>
          <Table>
            <THead>
              <TR>
                <TH>Nome</TH>
                <TH>Filtros</TH>
                <TH>Período</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {definitions.data.map((d) => (
                <TR key={d.id}>
                  <TD className="font-medium">{d.name}</TD>
                  <TD className="text-sm text-slate-600">{d.filtersLabel}</TD>
                  <TD className="text-sm">{d.params.from || d.params.to ? `${d.params.from ?? "…"} a ${d.params.to ?? "…"}` : "Últimas 12 semanas"}</TD>
                  <TD>
                    <div className="flex flex-wrap justify-end gap-1">
                      <Button size="sm" variant="ghost" onClick={() => apply(d)}>
                        Aplicar
                      </Button>
                      <Button size="sm" variant="outline" disabled={generate.isPending} onClick={() => generate.mutate({ id: d.id, format: "pdf" })}>
                        PDF
                      </Button>
                      <Button size="sm" variant="outline" disabled={generate.isPending} onClick={() => generate.mutate({ id: d.id, format: "xlsx" })}>
                        XLSX
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`Eliminar ${d.name}`}
                        disabled={remove.isPending}
                        onClick={() => window.confirm(`Eliminar a definição «${d.name}»?`) && remove.mutate(d.id)}
                      >
                        <Trash2 className="h-4 w-4" aria-hidden="true" />
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Card>
      )}

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
