import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getCfd } from "@/api/delivery";
import { CfdChart } from "@/charts/CfdChart";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDateTime } from "@/lib/format";

const EXTRA_KEYS = ["from", "to", "group"];
// Os snapshots só guardam ids por estado/coluna: filtra-se pelos atributos estáveis dos cartões.
const HIDDEN_FILTERS = ["state", "status", "columnId", "laneId", "blocked", "createdFrom", "createdTo", "overdue", "dueSoon"];

export function CfdPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);

  const cfd = useQuery({
    queryKey: ["cfd", boardId, query],
    queryFn: () => getCfd(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const c = cfd.data;
  const group = (query as { group?: string }).group ?? "status";

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Cumulative Flow Diagram</h1>
        {c && <DataAsOf dataAsOf={c.dataAsOf} stale={c.stale} />}
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex flex-wrap items-end gap-3">
            <PeriodControls query={query} setFilter={setFilter} effective={c?.period} showGranularity={false} />
            <div className="space-y-1">
              <Label htmlFor="cfd-group">Séries</Label>
              <Select id="cfd-group" className="w-36" value={group} onChange={(e) => setFilter("group", e.target.value)}>
                <option value="status">Por estado</option>
                <option value="column">Por coluna</option>
              </Select>
            </div>
          </div>
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={cfd.error} />
      {!c ? (
        !cfd.error && <Loading />
      ) : (
        <>
          <p className="text-sm text-slate-600">
            Um ponto por dia (último snapshot recolhido nesse dia), só com cartões ativos.{" "}
            {c.snapshotsSince ? `Histórico recolhido desde ${formatDateTime(c.snapshotsSince)}.` : "Ainda não há histórico recolhido."}
            {c.filtered && " Filtros aplicados com os atributos atuais dos cartões."}
          </p>
          {!c.available && <Alert variant="warning">CFD indisponível: {c.reason}.</Alert>}
          <CfdChart cfd={c} />
        </>
      )}
    </div>
  );
}
