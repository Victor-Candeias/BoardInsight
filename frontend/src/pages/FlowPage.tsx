import { useState } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { PERIOD_KEYS } from "@/api/dashboard";
import { getFlow, type MetricSummary } from "@/api/delivery";
import { DistributionChart } from "@/charts/DistributionChart";
import { CycleTrendChart, TimeScatterChart } from "@/charts/FlowCharts";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDays } from "@/lib/format";

const EXTRA_KEYS = [...PERIOD_KEYS];
const HIDDEN_FILTERS = ["state", "status", "createdFrom", "createdTo", "overdue", "dueSoon"];

function hint(m: MetricSummary) {
  if (!m.available) return m.reason;
  return `${m.count} cartões${m.smallSample ? " · amostra pequena" : ""}`;
}

function MetricRow({ label, m }: { label: string; m: MetricSummary }) {
  return (
    <TR>
      <TD className="font-medium">{label}</TD>
      {m.available ? (
        <>
          <TD>{m.count}</TD>
          <TD>{formatDays(m.p50)}</TD>
          <TD>{formatDays(m.p85)}</TD>
          <TD>{formatDays(m.p95)}</TD>
          <TD>{formatDays(m.mean)}</TD>
          <TD>{formatDays(m.max)}</TD>
        </>
      ) : (
        <TD colSpan={6} className="text-slate-500">
          Indisponível: {m.reason}
        </TD>
      )}
    </TR>
  );
}

export function FlowPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const [metric, setMetric] = useState<"cycleDays" | "leadDays">("cycleDays");

  const flow = useQuery({
    queryKey: ["flow", boardId, query],
    queryFn: () => getFlow(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const f = flow.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Fluxo</h1>
        {f && <DataAsOf dataAsOf={f.dataAsOf} stale={f.stale} />}
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <PeriodControls query={query} setFilter={setFilter} effective={f?.period} />
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={flow.error} />
      {!f ? (
        !flow.error && <Loading />
      ) : (
        <>
          <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiCard label="WIP (em curso)" value={f.wip.total} hint={`${f.wip.blocked} bloqueados`} to="/cards?status=in_progress" />
            <KpiCard label="Cycle time P50 (dias)" digits={1} value={f.cycleTime.p50} hint={hint(f.cycleTime)} />
            <KpiCard label="Cycle time P85 (dias)" digits={1} value={f.cycleTime.p85} hint={f.cycleTime.available ? `P95 ${formatDays(f.cycleTime.p95)}` : undefined} />
            <KpiCard label="Lead time P50 (dias)" digits={1} value={f.leadTime.p50} hint={hint(f.leadTime)} />
            <KpiCard label="Lead time P85 (dias)" digits={1} value={f.leadTime.p85} hint={f.leadTime.available ? `P95 ${formatDays(f.leadTime.p95)}` : undefined} />
            <KpiCard
              label="WIP acima do P85"
              value={f.aging.threshold === null ? null : f.aging.aboveThreshold}
              tone="warning"
              hint={f.aging.threshold === null ? "sem referência de cycle time" : `idade > ${formatDays(f.aging.threshold)}`}
            />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>Percentis (dias)</CardTitle>
              <CardDescription>
                Lead time = fim − criação; cycle time = fim − início. Interpolação linear; menos de 5 valores = amostra pequena.
                {f.cycleTime.withoutStart > 0 && ` ${f.cycleTime.withoutStart} concluídos sem data de início ficam fora do cycle time.`}
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Percentis">
                <THead>
                  <TR>
                    <TH>Métrica</TH>
                    <TH>Cartões</TH>
                    <TH>P50</TH>
                    <TH>P85</TH>
                    <TH>P95</TH>
                    <TH>Média</TH>
                    <TH>Máx.</TH>
                  </TR>
                </THead>
                <TBody>
                  <MetricRow label="Lead time" m={f.leadTime} />
                  <MetricRow label="Cycle time" m={f.cycleTime} />
                  <MetricRow label="Idade do WIP" m={f.aging} />
                </TBody>
              </Table>
            </CardContent>
          </Card>

          <div className="flex items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="flow-metric">Dispersão</Label>
              <Select id="flow-metric" className="w-40" value={metric} onChange={(e) => setMetric(e.target.value as "cycleDays" | "leadDays")}>
                <option value="cycleDays">Cycle time</option>
                <option value="leadDays">Lead time</option>
              </Select>
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <TimeScatterChart flow={f} metric={metric} />
            <CycleTrendChart trend={f.trend} />
            <DistributionChart title="WIP por coluna" data={f.wip.byColumn} />
            <DistributionChart title="WIP por responsável" data={f.wip.byOwner} color="#7c3aed" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Aging do trabalho em curso</CardTitle>
              <CardDescription>Idade = agora − início. Sem data de início usa a entrada na posição atual (*).</CardDescription>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Aging do WIP">
                <THead>
                  <TR>
                    <TH>ID</TH>
                    <TH>Título</TH>
                    <TH>Coluna</TH>
                    <TH>Responsável</TH>
                    <TH>Idade</TH>
                    <TH />
                  </TR>
                </THead>
                <TBody>
                  {f.aging.items.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="py-6 text-center text-slate-500">
                        Sem trabalho em curso.
                      </TD>
                    </TR>
                  )}
                  {f.aging.items.map((a) => (
                    <TR key={a.cardId}>
                      <TD>
                        <Link to={`/cards/${a.cardId}`} className="font-mono text-sky-700 hover:underline">
                          {a.customId || a.cardId}
                        </Link>
                      </TD>
                      <TD>{a.title}</TD>
                      <TD>{a.columnName ?? "—"}</TD>
                      <TD>{a.ownerName ?? <span className="text-slate-400">—</span>}</TD>
                      <TD>
                        {formatDays(a.ageDays)}
                        {a.estimated && " *"}
                      </TD>
                      <TD className="space-x-1">
                        {a.aboveP85 && <Badge variant="warning">Acima do P85</Badge>}
                        {a.isBlocked && <Badge variant="danger">Bloqueado</Badge>}
                      </TD>
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
