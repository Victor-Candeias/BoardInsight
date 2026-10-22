import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CARD_FILTER_KEYS, type CardQuery } from "@/api/cards";
import { getDashboard, PERIOD_KEYS } from "@/api/dashboard";
import { DistributionChart } from "@/charts/DistributionChart";
import { TimelineChart } from "@/charts/TimelineChart";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Card, CardContent } from "@/components/ui/card";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate } from "@/lib/format";

const EXTRA_KEYS = [...PERIOD_KEYS];
const HIDDEN_FILTERS = ["state", "createdFrom", "createdTo"];

/** Liga um KPI à lista de cartões com os filtros atuais e os do indicador. */
function cardsLink(query: CardQuery, extra: Record<string, string | null>) {
  const params = new URLSearchParams();
  for (const key of CARD_FILTER_KEYS) {
    const value = query[key];
    if (value) params.set(key, value);
  }
  for (const [key, value] of Object.entries(extra)) {
    if (value) params.set(key, value);
    else params.delete(key);
  }
  const qs = params.toString();
  return `/cards${qs ? `?${qs}` : ""}`;
}

export function DashboardPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);

  const dashboard = useQuery({
    queryKey: ["dashboard", boardId, query],
    queryFn: () => getDashboard(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const d = dashboard.data;
  const k = d?.kpis;
  const period = d?.period;
  const periodHint = period ? `${formatDate(period.from)} – ${formatDate(period.to)}` : undefined;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        {d && !d.stale && <DataAsOf dataAsOf={d.dataAsOf} stale={false} />}
      </div>
      {d && (d.stale || !d.dataAsOf) && <DataAsOf dataAsOf={d.dataAsOf} stale={d.stale} />}
      <Card>
        <CardContent className="space-y-3 pt-6">
          <PeriodControls query={query} setFilter={setFilter} effective={period} />
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={dashboard.error} />
      {dashboard.isLoading || !d || !k ? (
        !dashboard.error && <Loading />
      ) : (
        <>
          <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <KpiCard label="Cartões ativos" value={k.open} to={cardsLink(query, { open: "true" })} />
            <KpiCard label="Backlog" value={k.backlog} to={cardsLink(query, { status: "backlog" })} />
            <KpiCard label="A fazer" value={k.todo} to={cardsLink(query, { status: "todo" })} />
            <KpiCard label="Em curso" value={k.inProgress} to={cardsLink(query, { status: "in_progress" })} />
            <KpiCard label="Concluídos (no board)" value={k.done} to={cardsLink(query, { status: "done" })} />
            <KpiCard label="Bloqueados" value={k.blocked} tone="danger" to={cardsLink(query, { blocked: "true" })} />
            <KpiCard label="Em atraso" value={k.overdue} tone="danger" to={cardsLink(query, { overdue: "true" })} />
            <KpiCard label="Prazo ≤ 7 dias" value={k.dueSoon} tone="warning" to={cardsLink(query, { dueSoon: "true" })} />
            <KpiCard label="Sem responsável" value={k.unassigned} tone="warning" to={cardsLink(query, { unassigned: "true", ownerUserId: null })} />
            <KpiCard
              label="Criados no período"
              value={k.createdInPeriod}
              hint={periodHint}
              to={period && cardsLink(query, { state: "all", status: null, createdFrom: period.from, createdTo: period.to })}
            />
            <KpiCard
              label="Concluídos no período"
              value={k.completedInPeriod}
              hint={periodHint}
              to={period && cardsLink(query, { state: "all", status: null, endedFrom: period.from, endedTo: period.to })}
            />
          </section>
          <TimelineChart title="Criados vs. concluídos" data={d.timeline} />
          <div className="grid gap-4 lg:grid-cols-2">
            <DistributionChart title="Por estado" data={d.distributions.status} />
            <DistributionChart title="Por coluna" data={d.distributions.column} />
            <DistributionChart title="Por responsável" data={d.distributions.owner} color="#7c3aed" />
            <DistributionChart title="Por tipo" data={d.distributions.type} color="#0d9488" />
            <DistributionChart title="Por prioridade" data={d.distributions.priority} color="#dc2626" />
            <DistributionChart title="Por lane" data={d.distributions.lane} color="#64748b" />
          </div>
        </>
      )}
    </div>
  );
}
