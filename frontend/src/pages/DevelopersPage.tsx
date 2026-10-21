import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { PERIOD_KEYS } from "@/api/dashboard";
import { getDevelopers, type DeveloperRow } from "@/api/delivery";
import { CompletedByPersonChart, OpenWorkChart } from "@/charts/DeveloperCharts";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDays, formatNumber } from "@/lib/format";

const EXTRA_KEYS = [...PERIOD_KEYS];
const HIDDEN_FILTERS = ["state", "status", "ownerUserId", "createdFrom", "createdTo", "overdue", "dueSoon"];

const ownerParam = (d: DeveloperRow) => (d.userId === null ? "unassigned=true" : `ownerUserId=${d.userId}`);

function Count({ value, to, tone }: { value: number; to: string; tone?: string }) {
  if (!value) return <span className="text-slate-400">0</span>;
  return (
    <Link to={to} className={tone ?? "text-sky-700 hover:underline"}>
      {formatNumber(value)}
    </Link>
  );
}

export function DevelopersPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);

  const developers = useQuery({
    queryKey: ["developers", boardId, query],
    queryFn: () => getDevelopers(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const d = developers.data;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Developers</h1>
        {d && <DataAsOf dataAsOf={d.dataAsOf} stale={d.stale} />}
      </div>
      {d && <Alert variant="info">{d.disclaimer}</Alert>}
      <Card>
        <CardContent className="space-y-3 pt-6">
          <PeriodControls query={query} setFilter={setFilter} effective={d?.period} />
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={developers.error} />
      {!d ? (
        !developers.error && <Loading />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Por pessoa</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Trabalho por pessoa">
                <THead>
                  <TR>
                    <TH>Pessoa</TH>
                    <TH>Backlog</TH>
                    <TH>A fazer</TH>
                    <TH>Em curso (WIP)</TH>
                    <TH>Bloqueados</TH>
                    <TH>Em atraso</TH>
                    <TH>Co-responsável</TH>
                    <TH>Idade média WIP</TH>
                    <TH>Idade máx. WIP</TH>
                    <TH>Concluídos</TH>
                    <TH>Tamanho concl.</TH>
                  </TR>
                </THead>
                <TBody>
                  {d.developers.length === 0 && (
                    <TR>
                      <TD colSpan={11} className="py-6 text-center text-slate-500">
                        Sem cartões para os filtros escolhidos.
                      </TD>
                    </TR>
                  )}
                  {d.developers.map((dev) => {
                    const cards = (extra = "") => `/cards?${ownerParam(dev)}${extra}`;
                    const estimated = dev.agingEstimated ? " *" : "";
                    return (
                      <TR key={String(dev.userId)}>
                        <TD className="font-medium">{dev.name}</TD>
                        <TD>
                          <Count value={dev.backlog} to={cards("&status=backlog")} />
                        </TD>
                        <TD>
                          <Count value={dev.todo} to={cards("&status=todo")} />
                        </TD>
                        <TD>
                          <Count value={dev.inProgress} to={cards("&status=in_progress")} />
                        </TD>
                        <TD>
                          <Count value={dev.blocked} to={cards("&blocked=true")} tone="text-red-700 hover:underline" />
                        </TD>
                        <TD>
                          <Count value={dev.overdue} to={cards("&overdue=true")} tone="text-red-700 hover:underline" />
                        </TD>
                        <TD>{formatNumber(dev.coOwnedOpen)}</TD>
                        <TD>{dev.avgAgingDays === null ? "—" : `${formatDays(dev.avgAgingDays)}${estimated}`}</TD>
                        <TD>{dev.maxAgingDays === null ? "—" : `${formatDays(dev.maxAgingDays)}${estimated}`}</TD>
                        <TD>
                          <Count
                            value={dev.completed}
                            to={cards(`&state=all&endedFrom=${d.period.from}&endedTo=${d.period.to}`)}
                          />
                        </TD>
                        <TD>{formatNumber(dev.completedSize, 1)}</TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
              {d.developers.some((dev) => dev.agingEstimated) && (
                <p className="mt-2 text-xs text-slate-500">* Estimado a partir da entrada na posição atual (cartões sem data de início).</p>
              )}
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <OpenWorkChart data={d.developers} />
            <CompletedByPersonChart data={d} />
          </div>
        </>
      )}
    </div>
  );
}
