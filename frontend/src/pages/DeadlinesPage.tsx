import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getDeadlines, type DeadlineList } from "@/api/delivery";
import { DistributionChart } from "@/charts/DistributionChart";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { PriorityBadge, StatusBadge } from "@/components/CardBadges";
import { DataAsOf } from "@/components/DataAsOf";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate, formatDays } from "@/lib/format";

const HIDDEN_FILTERS = ["state", "status", "createdFrom", "createdTo", "overdue", "dueSoon"];

function DeadlineTable({ title, list, empty }: { title: string; list: DeadlineList; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {title} ({list.total})
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto">
        <Table aria-label={title}>
          <THead>
            <TR>
              <TH>ID</TH>
              <TH>Título</TH>
              <TH>Estado</TH>
              <TH>Responsável</TH>
              <TH>Prioridade</TH>
              <TH>Prazo</TH>
              <TH>Dias</TH>
            </TR>
          </THead>
          <TBody>
            {list.items.length === 0 && (
              <TR>
                <TD colSpan={7} className="py-6 text-center text-slate-500">
                  {empty}
                </TD>
              </TR>
            )}
            {list.items.map((c) => (
              <TR key={c.cardId}>
                <TD>
                  <Link to={`/cards/${c.cardId}`} className="font-mono text-sky-700 hover:underline">
                    {c.customId || c.cardId}
                  </Link>
                </TD>
                <TD>{c.title || "(sem título)"}</TD>
                <TD>
                  <StatusBadge card={c} />
                </TD>
                <TD>{c.ownerName ?? <span className="text-slate-400">—</span>}</TD>
                <TD>
                  <PriorityBadge card={c} />
                </TD>
                <TD>{formatDate(c.deadline)}</TD>
                <TD className={c.daysToDeadline < 0 ? "font-medium text-red-700" : undefined}>{formatDays(c.daysToDeadline)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
        {list.truncated && <p className="mt-2 text-xs text-slate-500">Lista limitada aos primeiros {list.items.length} cartões.</p>}
      </CardContent>
    </Card>
  );
}

export function DeadlinesPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters();

  const deadlines = useQuery({
    queryKey: ["deadlines", boardId, query],
    queryFn: () => getDeadlines(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const d = deadlines.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Prazos</h1>
        {d && <DataAsOf dataAsOf={d.dataAsOf} stale={d.stale} />}
      </div>
      <Card>
        <CardContent className="pt-6">
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={deadlines.error} />
      {!d ? (
        !deadlines.error && <Loading />
      ) : (
        <>
          <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <KpiCard label="Em atraso" value={d.overdue.total} tone="danger" />
            <KpiCard label={`A vencer (≤ ${d.dueSoonDays} dias)`} value={d.dueSoon.total} tone="warning" />
            <KpiCard label="Abertos sem prazo" value={d.withoutDeadline} hint={`de ${d.openTotal} cartões abertos`} />
            <KpiCard label="Abertos" value={d.openTotal} />
          </section>
          <DeadlineTable title="Em atraso" list={d.overdue} empty="Nenhum cartão em atraso." />
          <DeadlineTable title={`A vencer nos próximos ${d.dueSoonDays} dias`} list={d.dueSoon} empty="Nenhum prazo nos próximos dias." />
          <DistributionChart title="Em atraso por responsável" data={d.overdueByOwner} color="#dc2626" />
        </>
      )}
    </div>
  );
}
