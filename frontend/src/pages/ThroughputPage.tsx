import { useRef, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { PERIOD_KEYS } from "@/api/dashboard";
import { getThroughput } from "@/api/delivery";
import { DistributionChart } from "@/charts/DistributionChart";
import { ThroughputChart } from "@/charts/ThroughputChart";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { ExportPdfButton } from "@/components/ExportPdfButton";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Card, CardContent } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate } from "@/lib/format";

const EXTRA_KEYS = [...PERIOD_KEYS];
const HIDDEN_FILTERS = ["state", "status", "open", "createdFrom", "createdTo", "overdue", "dueSoon"];

export function ThroughputPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const [measure, setMeasure] = useState<"count" | "size">("count");
  const pageRef = useRef<HTMLDivElement>(null);

  const throughput = useQuery({
    queryKey: ["throughput", boardId, query],
    queryFn: () => getThroughput(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const t = throughput.data;
  const unit = { day: "dia", week: "semana", month: "mês" }[t?.period.granularity ?? "week"];

  return (
    <div ref={pageRef} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Throughput</h1>
        <div className="flex flex-wrap items-center gap-3">
          {t && <DataAsOf dataAsOf={t.dataAsOf} stale={t.stale} />}
          <ExportPdfButton target={pageRef} page="throughput" disabled={!t} />
        </div>
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex flex-wrap items-end gap-3">
            <PeriodControls query={query} setFilter={setFilter} effective={t?.period} />
            <div className="space-y-1">
              <Label htmlFor="t-measure">Medida</Label>
              <Select id="t-measure" className="w-36" value={measure} onChange={(e) => setMeasure(e.target.value as "count" | "size")}>
                <option value="count">Cartões</option>
                <option value="size">Tamanho</option>
              </Select>
            </div>
          </div>
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={throughput.error} />
      {!t ? (
        !throughput.error && <Loading />
      ) : (
        <>
          <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-3">
            <KpiCard label="Concluídos no período" value={t.total} hint={`${formatDate(t.period.from)} – ${formatDate(t.period.to)}`} />
            <KpiCard label="Tamanho concluído" value={t.totalSize} />
            <KpiCard label={`Média por ${unit}`} value={t.averagePerBucket} hint="Exclui intervalos incompletos" />
          </section>
          <ThroughputChart data={t.series} measure={measure} average={t.averagePerBucket} />
          {t.series.some((s) => s.partial) && (
            <p className="text-xs text-slate-500">Barras claras: intervalos cortados pelo início ou fim do período.</p>
          )}
          <DistributionChart title="Concluídos por tipo" data={t.byType} color="#0d9488" />
          <p className="text-xs text-slate-500">
            Conta cartões com data de fim no período, incluindo arquivados (até 183 dias); descartados não contam.
          </p>
        </>
      )}
    </div>
  );
}
