import { useState } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getSprint, getSprints, type SprintCardRow } from "@/api/sprints";
import { BurndownChart, VelocityChart } from "@/charts/SprintCharts";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { KpiCard } from "@/components/KpiCard";
import { NoBoard } from "@/components/NoBoard";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { SprintConfigForm } from "@/components/SprintConfigForm";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label, Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";

const EXTRA_KEYS = ["sprint"];
const HIDDEN_FILTERS = ["state", "status", "columnId", "laneId", "blocked", "createdFrom", "createdTo", "overdue", "dueSoon"];

function CardsTable({ label, rows, empty }: { label: string; rows: SprintCardRow[]; empty: string }) {
  return (
    <Table aria-label={label}>
      <THead>
        <TR>
          <TH>ID</TH>
          <TH>Título</TH>
          <TH>Tamanho</TH>
          <TH>Estado atual</TH>
          <TH />
        </TR>
      </THead>
      <TBody>
        {rows.length === 0 && (
          <TR>
            <TD colSpan={5} className="py-6 text-center text-slate-500">
              {empty}
            </TD>
          </TR>
        )}
        {rows.map((r) => (
          <TR key={r.cardId}>
            <TD>
              <Link to={`/cards/${r.cardId}`} className="font-mono text-sky-700 hover:underline">
                {r.customId || r.cardId}
              </Link>
            </TD>
            <TD>{r.title ?? "—"}</TD>
            <TD>{r.size ?? "—"}</TD>
            <TD>{r.statusLabel ?? r.status ?? "—"}</TD>
            <TD>{r.doneInSprint && <Badge variant="success">Concluído na sprint</Badge>}</TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}

export function SprintsPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const [showConfig, setShowConfig] = useState(false);
  const { sprint: selected, ...filters } = query as typeof query & { sprint?: string };

  const list = useQuery({
    queryKey: ["sprints", boardId, filters],
    queryFn: () => getSprints(boardId!, filters),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });
  const sprints = list.data?.sprints ?? [];
  const sprintId = selected && sprints.some((s) => s.id === selected) ? selected : sprints.at(-1)?.id;
  const detail = useQuery({
    queryKey: ["sprints", boardId, "detail", sprintId, filters],
    queryFn: () => getSprint(boardId!, sprintId!, filters),
    enabled: boardId !== null && !!sprintId,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const l = list.data;
  const d = detail.data?.id === sprintId ? detail.data : undefined;
  const configured = l && (l.config.cadence || l.config.explicit.length > 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-2xl font-semibold">Sprints</h1>
        {l && <DataAsOf dataAsOf={l.dataAsOf} stale={l.stale} />}
      </div>
      <ErrorAlert error={list.error ?? detail.error} />
      {!l ? (
        !list.error && <Loading />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Configuração</CardTitle>
              <CardDescription>
                O Businessmap não tem sprints: defina uma cadência fixa ou uma lista explícita (prevalece sobre a cadência).{" "}
                {configured && (
                  <button type="button" className="text-sky-700 hover:underline" onClick={() => setShowConfig((v) => !v)}>
                    {showConfig ? "Esconder" : "Alterar"}
                  </button>
                )}
              </CardDescription>
            </CardHeader>
            {(!configured || showConfig) && (
              <CardContent>
                <SprintConfigForm key={JSON.stringify(l.config)} boardId={boardId} config={l.config} />
              </CardContent>
            )}
          </Card>

          {configured && sprints.length === 0 && <Alert variant="info">Ainda não começou nenhuma sprint.</Alert>}
          {sprints.length > 0 && (
            <>
              <Card>
                <CardContent className="space-y-3 pt-6">
                  <div className="space-y-1">
                    <Label htmlFor="sprint-select">Sprint</Label>
                    <Select id="sprint-select" className="w-72" value={sprintId} onChange={(e) => setFilter("sprint", e.target.value)}>
                      {[...sprints].reverse().map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name} ({formatDate(s.start)} – {formatDate(s.end)}){s.state === "current" ? " · atual" : ""}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
                </CardContent>
              </Card>

              {d && (
                <>
                  <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                    <KpiCard label="Concluídos na sprint" value={d.completed} hint={`tamanho ${formatNumber(d.completedSize)}`} />
                    <KpiCard label="Compromisso" value={d.committed} hint={d.commitmentAvailable ? `no início (${formatDateTime(d.commitmentAt)})` : d.commitmentReason} />
                    <KpiCard label="Compromisso concluído" value={d.committedDone} />
                    <KpiCard label="Cumprimento (%)" value={d.completionRate === null ? null : d.completionRate * 100} />
                    <KpiCard label="Adicionados depois" value={d.commitmentAvailable ? d.added.length : null} tone="warning" />
                    <KpiCard
                      label="Velocity média"
                      digits={1}
                      value={l.averageVelocity}
                      hint={l.averageVelocitySprints ? `últimas ${l.averageVelocitySprints} sprints terminadas` : "sem sprints terminadas"}
                    />
                  </section>
                  {!d.commitmentAvailable && (
                    <Alert variant="warning">Compromisso e burndown indisponíveis: {d.commitmentReason}. A velocity continua disponível.</Alert>
                  )}
                  <div className="grid gap-4 lg:grid-cols-2">
                    <BurndownChart sprint={d} />
                    <VelocityChart sprints={sprints} />
                  </div>
                  {d.commitmentAvailable && (
                    <div className="grid gap-4 lg:grid-cols-2">
                      <Card>
                        <CardHeader>
                          <CardTitle>Compromisso</CardTitle>
                        </CardHeader>
                        <CardContent className="overflow-x-auto">
                          <CardsTable label="Compromisso da sprint" rows={d.commitment} empty="Sem cartões no compromisso." />
                        </CardContent>
                      </Card>
                      <Card>
                        <CardHeader>
                          <CardTitle>Adicionados durante a sprint</CardTitle>
                        </CardHeader>
                        <CardContent className="overflow-x-auto">
                          <CardsTable label="Adicionados durante a sprint" rows={d.added} empty="Sem alterações de âmbito." />
                        </CardContent>
                      </Card>
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
