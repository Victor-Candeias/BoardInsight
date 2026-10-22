import { useRef, useState } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Clock, OctagonAlert, RotateCcw, UserX, Users, type LucideIcon } from "lucide-react";
import { getAttention, type AttentionItem, type AttentionReason } from "@/api/delivery";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { DataAsOf } from "@/components/DataAsOf";
import { ExportPdfButton } from "@/components/ExportPdfButton";
import { NoBoard } from "@/components/NoBoard";
import { PeriodControls } from "@/components/PeriodControls";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate, formatDays, formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const EXTRA_KEYS = ["from", "to"];
const HIDDEN_FILTERS = ["state", "status", "open", "blocked", "overdue", "dueSoon", "createdFrom", "createdTo", "endedFrom", "endedTo"];

const REASONS: Record<AttentionReason, { label: string; icon: LucideIcon; variant: "danger" | "warning" | "info" | "default" }> = {
  blocked: { label: "Bloqueado", icon: OctagonAlert, variant: "danger" },
  overdue: { label: "Em atraso", icon: AlertTriangle, variant: "danger" },
  aging: { label: "Aging > P85", icon: Clock, variant: "warning" },
  dueSoon: { label: "Prazo próximo", icon: CalendarClock, variant: "info" },
  unassigned: { label: "Sem responsável", icon: UserX, variant: "default" },
};

function detail(item: AttentionItem): string[] {
  const out: string[] = [];
  if (item.reasons.includes("blocked"))
    out.push(`bloqueado há ${formatDays(item.blockedDays)}${item.blockReason ? ` (${item.blockReason})` : ""}`);
  if (item.reasons.includes("overdue") || item.reasons.includes("dueSoon"))
    out.push(`prazo ${formatDate(item.deadline)} (${formatDays(item.daysToDeadline)})`);
  if (item.ageDays !== null) out.push(`em curso há ${formatDays(item.ageDays)}${item.ageEstimated ? " *" : ""}`);
  return out;
}

interface TileProps {
  reason: AttentionReason;
  value: number;
  hint: string;
  active: boolean;
  onToggle: () => void;
}

function ReasonTile({ reason, value, hint, active, onToggle }: TileProps) {
  const { label, icon: Icon, variant } = REASONS[reason];
  const tone = !value ? "text-slate-900" : variant === "danger" ? "text-red-700" : variant === "warning" ? "text-amber-700" : "text-sky-700";
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      aria-label={`${label}: ${value}`}
      className={cn(
        "rounded-xl border bg-surface p-4 text-left shadow-sm transition-colors hover:border-sky-300 focus-visible:outline-2 focus-visible:outline-sky-500",
        active ? "border-sky-500 ring-1 ring-sky-500" : "border-slate-200",
      )}
    >
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
        <Icon className="h-4 w-4" aria-hidden />
        {label}
      </div>
      <div className={cn("mt-1 text-2xl font-semibold", tone)}>{formatNumber(value)}</div>
      <div className="text-xs text-slate-500">{hint}</div>
    </button>
  );
}

export function AttentionPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const [reason, setReason] = useState<AttentionReason | null>(null);
  const pageRef = useRef<HTMLDivElement>(null);

  const attention = useQuery({
    queryKey: ["attention", boardId, query],
    queryFn: () => getAttention(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  if (boardId === null) return <NoBoard />;
  const a = attention.data;
  const items = a ? (reason ? a.items.filter((i) => i.reasons.includes(reason)) : a.items) : [];
  const ref = a?.agingReference;

  return (
    <div ref={pageRef} className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Atenção</h1>
          <p className="text-sm text-slate-500">O que exige ação hoje: bloqueios, trabalho envelhecido, prazos, WIP e responsáveis.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {a && <DataAsOf dataAsOf={a.dataAsOf} stale={a.stale} />}
          <ExportPdfButton target={pageRef} page="atencao" disabled={!a} />
        </div>
      </div>
      <Card>
        <CardContent className="space-y-3 pt-6">
          <PeriodControls query={query} setFilter={setFilter} effective={a?.period} showGranularity={false} />
          <p className="text-xs text-slate-500">O período define a referência de aging (P85 do cycle time) e as reaberturas.</p>
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} hide={HIDDEN_FILTERS} />
        </CardContent>
      </Card>
      <ErrorAlert error={attention.error} />
      {!a ? (
        !attention.error && <Loading />
      ) : (
        <>
          <section aria-label="Motivos de atenção" className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <ReasonTile reason="blocked" value={a.summary.blocked} hint="cartões abertos bloqueados" active={reason === "blocked"} onToggle={() => setReason(reason === "blocked" ? null : "blocked")} />
            <ReasonTile reason="overdue" value={a.summary.overdue} hint="prazo ultrapassado" active={reason === "overdue"} onToggle={() => setReason(reason === "overdue" ? null : "overdue")} />
            <ReasonTile
              reason="aging"
              value={a.summary.aging}
              hint={ref?.p85 != null ? `em curso há mais de ${formatDays(ref.p85)}` : "sem referência no período"}
              active={reason === "aging"}
              onToggle={() => setReason(reason === "aging" ? null : "aging")}
            />
            <ReasonTile reason="dueSoon" value={a.summary.dueSoon} hint={`prazo nos próximos ${a.dueSoonDays} dias`} active={reason === "dueSoon"} onToggle={() => setReason(reason === "dueSoon" ? null : "dueSoon")} />
            <ReasonTile reason="unassigned" value={a.summary.unassigned} hint="a fazer ou em curso" active={reason === "unassigned"} onToggle={() => setReason(reason === "unassigned" ? null : "unassigned")} />
          </section>

          <Card>
            <CardHeader className="flex-row flex-wrap items-baseline justify-between">
              <div>
                <CardTitle>
                  Cartões que exigem ação ({reason ? `${items.length} de ${a.total}` : a.total})
                </CardTitle>
                <CardDescription>
                  Ordenados por urgência. {a.total} de {a.openTotal} cartões abertos.
                  {reason && (
                    <>
                      {" "}
                      <button type="button" className="text-sky-700 hover:underline" onClick={() => setReason(null)}>
                        Mostrar todos
                      </button>
                    </>
                  )}
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table aria-label="Cartões que exigem ação">
                <THead>
                  <TR>
                    <TH>ID</TH>
                    <TH>Título</TH>
                    <TH>Motivos</TH>
                    <TH>Coluna</TH>
                    <TH>Responsável</TH>
                    <TH>Detalhe</TH>
                  </TR>
                </THead>
                <TBody>
                  {items.length === 0 && (
                    <TR>
                      <TD colSpan={6} className="py-6 text-center text-slate-500">
                        Nada a assinalar para os filtros escolhidos.
                      </TD>
                    </TR>
                  )}
                  {items.map((i) => (
                    <TR key={i.cardId}>
                      <TD>
                        <Link to={`/cards/${i.cardId}`} className="font-mono text-sky-700 hover:underline">
                          {i.customId || i.cardId}
                        </Link>
                      </TD>
                      <TD className="max-w-md">{i.title || "(sem título)"}</TD>
                      <TD>
                        <span className="inline-flex flex-wrap gap-1">
                          {i.reasons.map((r) => (
                            <Badge key={r} variant={REASONS[r].variant}>
                              {REASONS[r].label}
                            </Badge>
                          ))}
                        </span>
                      </TD>
                      <TD>{i.columnName ?? i.statusLabel}</TD>
                      <TD>{i.ownerName ?? <span className="text-slate-400">—</span>}</TD>
                      <TD className="text-xs text-slate-600">{detail(i).join(" · ")}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
              {a.truncated && <p className="mt-2 text-xs text-slate-500">Lista limitada aos primeiros {a.items.length} cartões.</p>}
              {a.items.some((i) => i.ageEstimated) && (
                <p className="mt-2 text-xs text-slate-500">* Idade estimada pela posição atual (cartão sem data de início).</p>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-4 w-4" aria-hidden />
                  WIP alto por pessoa (mais de {a.wipLimit} em curso)
                </CardTitle>
              </CardHeader>
              <CardContent>
                {a.people.length === 0 ? (
                  <p className="text-sm text-slate-500">Ninguém acima do limite.</p>
                ) : (
                  <ul aria-label="WIP alto por pessoa" className="divide-y divide-slate-100">
                    {a.people.map((p) => (
                      <li key={p.userId} className="flex items-center justify-between py-2 text-sm">
                        <span>{p.name}</span>
                        <Link to={`/cards?ownerUserId=${p.userId}&status=in_progress`} className="font-medium text-amber-700 hover:underline">
                          {p.inProgress} em curso
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                <Link to="/developers" className="mt-3 inline-block text-xs text-sky-700 hover:underline">
                  Ver distribuição por pessoa
                </Link>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <RotateCcw className="h-4 w-4" aria-hidden />
                  Referências do período
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-slate-600">
                <p>
                  Cycle time P85:{" "}
                  {ref?.p85 != null ? (
                    <>
                      <span className="font-medium text-slate-900">{formatDays(ref.p85)}</span> ({ref.count} cartões concluídos
                      {ref.smallSample ? ", amostra pequena" : ""})
                    </>
                  ) : (
                    "sem cartões concluídos com data de início — aging não avaliado"
                  )}
                  .{" "}
                  <Link to="/flow" className="text-sky-700 hover:underline">
                    Ver fluxo
                  </Link>
                </p>
                <p>
                  Cartões reabertos:{" "}
                  {a.reopensAvailable ? <span className="font-medium text-slate-900">{a.summary.reopenedCards}</span> : "histórico ainda não recolhido"}.{" "}
                  <Link to="/blockers" className="text-sky-700 hover:underline">
                    Ver bloqueios e qualidade
                  </Link>
                </p>
                <p>
                  <Link to="/deadlines" className="text-sky-700 hover:underline">
                    Ver todos os prazos
                  </Link>
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
