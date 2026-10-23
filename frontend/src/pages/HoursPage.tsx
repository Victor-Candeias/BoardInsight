import { useRef } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getHours, HOURS_KEYS, type HoursQuery } from "@/api/hours";
import { HoursChart } from "@/charts/HoursChart";
import { DataAsOf } from "@/components/DataAsOf";
import { ExportPdfButton } from "@/components/ExportPdfButton";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate, formatHours, formatNumber } from "@/lib/format";

const EXTRA_KEYS = [...HOURS_KEYS];

export function HoursPage() {
  const [boardId] = useActiveBoard();
  const { query: all, setFilter } = useCardFilters(EXTRA_KEYS);
  const pageRef = useRef<HTMLDivElement>(null);
  const params = all as Record<string, string | undefined>;
  const query: HoursQuery = Object.fromEntries(HOURS_KEYS.filter((k) => params[k]).map((k) => [k, params[k]]));
  const includeSubtasks = query.includeSubtasks !== "false";

  const hours = useQuery({
    queryKey: ["hours", boardId, query],
    queryFn: () => getHours(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const h = hours.data;
  const selectUser = (userId: number | null) => setFilter("userId", userId === null ? null : String(userId));

  return (
    <div ref={pageRef} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Horas</h1>
        <div className="flex flex-wrap items-center gap-3">
          {h && <DataAsOf dataAsOf={h.dataAsOf} stale={h.stale} />}
          <ExportPdfButton target={pageRef} page="horas" disabled={!h} />
        </div>
      </div>
      {h && <Alert variant="info">{h.disclaimer}</Alert>}
      <Card>
        <CardContent className="space-y-3 pt-6">
          <div className="flex flex-wrap items-end gap-3">
            <PeriodControls query={query} setFilter={setFilter} effective={h?.period} />
            <div className="space-y-1">
              <Label htmlFor="h-user">Utilizador</Label>
              <Select id="h-user" className="w-56" value={query.userId ?? ""} onChange={(e) => setFilter("userId", e.target.value || null)}>
                <option value="">Todos</option>
                {h?.users.map((u) => (
                  <option key={u.userId} value={String(u.userId)}>
                    {u.name}
                  </option>
                ))}
              </Select>
            </div>
            <label className="flex items-center gap-1 pb-2 text-sm">
              <input
                type="checkbox"
                checked={includeSubtasks}
                onChange={(e) => setFilter("includeSubtasks", e.target.checked ? null : "false")}
              />
              Incluir subtarefas
            </label>
          </div>
        </CardContent>
      </Card>
      <ErrorAlert error={hours.error} />
      {h && !h.available && (
        <Alert variant="warning">O tempo registado ainda não foi sincronizado para este board. Execute uma sincronização.</Alert>
      )}
      {h?.warning && <Alert variant="warning">{h.warning}</Alert>}
      {!h ? (
        !hours.error && <Loading />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <KpiCard label="Total de horas" value={h.totalSeconds} display={formatHours(h.totalSeconds)} hint="HH:mm" />
            <KpiCard label="Registos" value={h.entryCount} />
            <KpiCard label="Cartões" value={h.cardCount} />
            <KpiCard label="Pessoas" value={h.peopleCount} />
            <KpiCard
              label="Média por dia registado"
              value={h.dayCount}
              display={formatHours(h.dayCount ? h.totalSeconds / h.dayCount : 0)}
              hint={`${formatNumber(h.dayCount)} dias com registos`}
            />
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Horas por utilizador</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Horas por utilizador">
                <THead>
                  <TR>
                    <TH>Utilizador</TH>
                    <TH>Horas</TH>
                    <TH>Registos</TH>
                    <TH>Cartões</TH>
                    <TH>Dias</TH>
                    <TH>Média por dia</TH>
                  </TR>
                </THead>
                <TBody>
                  {h.byUser.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="py-6 text-center text-slate-500">
                        Sem horas registadas para os filtros escolhidos.
                      </TD>
                    </TR>
                  )}
                  {h.byUser.map((u) => (
                    <TR key={String(u.userId)}>
                      <TD className="font-medium">
                        {h.userId === null && u.userId !== null ? (
                          <button type="button" className="text-sky-700 hover:underline" onClick={() => selectUser(u.userId)}>
                            {u.name}
                          </button>
                        ) : (
                          u.name
                        )}
                      </TD>
                      <TD className="font-mono">{formatHours(u.seconds)}</TD>
                      <TD>{formatNumber(u.entries)}</TD>
                      <TD>{formatNumber(u.cards)}</TD>
                      <TD>{formatNumber(u.days)}</TD>
                      <TD className="font-mono">{formatHours(u.avgSecondsPerDay)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
          <HoursChart data={h} />
          <Card>
            <CardHeader>
              <CardTitle>Registos</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Registos de tempo">
                <THead>
                  <TR>
                    <TH>Data</TH>
                    <TH>Utilizador</TH>
                    <TH>Cartão</TH>
                    <TH>Horas</TH>
                    <TH>Comentário</TH>
                  </TR>
                </THead>
                <TBody>
                  {h.entries.length === 0 && (
                    <TR>
                      <TD colSpan={5} className="py-6 text-center text-slate-500">
                        Sem registos no período.
                      </TD>
                    </TR>
                  )}
                  {h.entries.map((e) => (
                    <TR key={e.loggedTimeId}>
                      <TD className="whitespace-nowrap">{formatDate(e.date)}</TD>
                      <TD>{e.userName}</TD>
                      <TD>
                        {e.cardId === null ? (
                          "—"
                        ) : (
                          <Link to={`/cards/${e.cardId}`} className="text-sky-700 hover:underline">
                            {e.customId || `#${e.cardId}`}
                            {e.title ? ` · ${e.title}` : ""}
                          </Link>
                        )}
                        {e.subtask && <span className="ml-2 rounded bg-slate-100 px-1 text-xs text-slate-600">Subtarefa</span>}
                      </TD>
                      <TD className="font-mono">{formatHours(e.seconds)}</TD>
                      <TD className="max-w-md truncate text-slate-600" title={e.comment ?? undefined}>
                        {e.comment || "—"}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {h.truncated && (
                <p className="mt-2 text-xs text-slate-500">
                  Mostrados os {formatNumber(h.entries.length)} registos mais recentes de {formatNumber(h.entryCount)}.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
