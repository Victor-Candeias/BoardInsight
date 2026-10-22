import { useRef } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { PERIOD_KEYS } from "@/api/dashboard";
import { getBlockers, getQuality } from "@/api/delivery";
import { BlockHistoryChart, ReopenChart } from "@/charts/BlockerCharts";
import { DistributionChart } from "@/charts/DistributionChart";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { ExportPdfButton } from "@/components/ExportPdfButton";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDateTime, formatDays, formatDuration, formatNumber } from "@/lib/format";

const EXTRA_KEYS = [...PERIOD_KEYS];
const HIDDEN_FILTERS = ["state", "status", "open", "blocked", "createdFrom", "createdTo", "overdue", "dueSoon"];

const percent = (v: number | null) => (v === null ? "—" : `${formatNumber(v * 100, 0)}%`);

function CardLink({ cardId, customId }: { cardId: number; customId: string | null }) {
  return (
    <Link to={`/cards/${cardId}`} className="font-mono text-sky-700 hover:underline">
      {customId || cardId}
    </Link>
  );
}

export function BlockersPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const options = { enabled: boardId !== null, placeholderData: keepPreviousData };
  const blockers = useQuery({ queryKey: ["blockers", boardId, query], queryFn: () => getBlockers(boardId!, query), ...options });
  const quality = useQuery({ queryKey: ["quality", boardId, query], queryFn: () => getQuality(boardId!, query), ...options });
  const pageRef = useRef<HTMLDivElement>(null);

  if (boardId === null) return <NoBoard />;
  const b = blockers.data;
  const q = quality.data;
  const since = b?.history.historySince;

  return (
    <div ref={pageRef} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Bloqueios e qualidade</h1>
        <div className="flex flex-wrap items-center gap-3">
          {b && <DataAsOf dataAsOf={b.dataAsOf} stale={b.stale} />}
          <ExportPdfButton target={pageRef} page="bloqueios-qualidade" disabled={!b || quality.isPending} />
        </div>
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <PeriodControls query={query} setFilter={setFilter} effective={b?.period} />
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={blockers.error ?? quality.error} />
      {!b || !q ? (
        !(blockers.error || quality.error) && <Loading />
      ) : (
        <>
          <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard label="Bloqueados agora" value={b.current.blocked} tone="danger" hint={`${percent(b.current.share)} de ${b.current.openTotal} em aberto`} to="/cards?blocked=true" />
            <KpiCard label="Tempo bloqueado P50 (dias)" digits={1} value={b.current.days.p50} hint={b.current.days.available ? `máx. ${formatDays(b.current.days.max)}` : b.current.days.reason} />
            <KpiCard label="Bloqueios no período" value={b.history.started} hint={`${b.history.resolved} resolvidos`} />
            <KpiCard label="Duração observada P50 (dias)" digits={1} value={b.history.resolvedDays.p50} hint={b.history.resolvedDays.available ? `${b.history.resolvedDays.count} desbloqueios` : b.history.resolvedDays.reason} />
            <KpiCard label="Reaberturas" value={q.reopens} tone="warning" hint={`${q.reopenedCards} cartões`} />
            <KpiCard label="Taxa de reabertura (%)" value={q.reopenRate === null ? null : q.reopenRate * 100} hint={`cartões reabertos ÷ ${q.completed} concluídos`} />
          </section>
          <p className="text-sm text-slate-600">
            {since
              ? `Histórico (bloqueios observados e reaberturas) recolhido desde ${formatDateTime(since)}; a precisão é o intervalo entre syncs. As reaberturas incluem também as transições devolvidas pela API.`
              : "Ainda não há histórico recolhido: só os bloqueios atuais estão disponíveis."}
          </p>
          {!q.available && <Alert variant="warning">Reaberturas indisponíveis: {q.reason}.</Alert>}

          <Card>
            <CardHeader>
              <CardTitle>Cartões bloqueados</CardTitle>
              <CardDescription>Tempo bloqueado e motivo atuais (Businessmap).</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Cartões bloqueados">
                <THead>
                  <TR>
                    <TH>ID</TH>
                    <TH>Título</TH>
                    <TH>Coluna</TH>
                    <TH>Responsável</TH>
                    <TH>Motivo</TH>
                    <TH>Bloqueado há</TH>
                  </TR>
                </THead>
                <TBody>
                  {b.current.items.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="py-6 text-center text-slate-500">
                        Sem cartões bloqueados.
                      </TD>
                    </TR>
                  )}
                  {b.current.items.map((i) => (
                    <TR key={i.cardId}>
                      <TD>
                        <CardLink cardId={i.cardId} customId={i.customId} />
                      </TD>
                      <TD>{i.title}</TD>
                      <TD>{i.columnName ?? "—"}</TD>
                      <TD>{i.ownerName ?? <span className="text-slate-400">—</span>}</TD>
                      <TD>
                        {i.reason ?? <span className="text-slate-400">Sem motivo</span>}
                        {i.comment && <div className="text-xs text-slate-500">{i.comment}</div>}
                      </TD>
                      <TD>{formatDuration(i.blockedSeconds)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {b.current.truncated && <p className="mt-2 text-xs text-slate-500">Lista truncada.</p>}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <DistributionChart title="Bloqueados por motivo" data={b.current.byReason} color="#dc2626" />
            <DistributionChart title="Bloqueados por responsável" data={b.current.byOwner} color="#7c3aed" />
            <DistributionChart title="Bloqueados por coluna" data={b.current.byColumn} />
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <BlockHistoryChart series={b.history.series} />
            <ReopenChart series={q.series} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Cartões reabertos</CardTitle>
              <CardDescription>Passagens de Concluído para Backlog, A fazer ou Em curso no período.</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Cartões reabertos">
                <THead>
                  <TR>
                    <TH>ID</TH>
                    <TH>Título</TH>
                    <TH>Coluna atual</TH>
                    <TH>Responsável</TH>
                    <TH>Reaberturas</TH>
                    <TH>Última</TH>
                  </TR>
                </THead>
                <TBody>
                  {q.items.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="py-6 text-center text-slate-500">
                        Sem reaberturas no período.
                      </TD>
                    </TR>
                  )}
                  {q.items.map((i) => (
                    <TR key={i.cardId}>
                      <TD>
                        <CardLink cardId={i.cardId} customId={i.customId} />
                      </TD>
                      <TD>{i.title ?? "—"}</TD>
                      <TD>{i.columnName ?? "—"}</TD>
                      <TD>{i.ownerName ?? <span className="text-slate-400">—</span>}</TD>
                      <TD>{i.reopens}</TD>
                      <TD>{formatDateTime(i.lastReopenedAt)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
