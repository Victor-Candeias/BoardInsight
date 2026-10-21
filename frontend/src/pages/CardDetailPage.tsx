import type { ReactNode } from "react";
import { Link, useParams } from "react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { getCard } from "@/api/cards";
import { CardFlags, PriorityBadge, StatusBadge } from "@/components/CardBadges";
import { NoBoard } from "@/components/NoBoard";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { formatDateTime, formatDuration, formatNumber } from "@/lib/format";

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 text-sm">{children ?? "—"}</dd>
    </div>
  );
}

const seconds = (start: string | null, end: string | null) =>
  start ? ((end ? new Date(end).getTime() : Date.now()) - new Date(start).getTime()) / 1000 : null;

export function CardDetailPage() {
  const [boardId] = useActiveBoard();
  const cardId = Number(useParams().cardId);
  const card = useQuery({
    queryKey: ["card", boardId, cardId],
    queryFn: () => getCard(boardId!, cardId),
    enabled: boardId !== null,
  });

  if (boardId === null) return <NoBoard />;
  if (card.isLoading) return <Loading />;
  if (card.error || !card.data) return <ErrorAlert error={card.error} />;
  const c = card.data;

  return (
    <div className="space-y-4">
      <Link to="/cards" className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800">
        <ArrowLeft className="h-4 w-4" /> Cartões
      </Link>
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{c.title || "(sem título)"}</h1>
          <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
            <span className="font-mono">{c.customId || `#${c.cardId}`}</span>
            <StatusBadge card={c} />
            <PriorityBadge card={c} />
            <CardFlags card={c} />
          </div>
        </div>
        <a
          href={c.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100"
        >
          Abrir no Businessmap <ExternalLink className="h-4 w-4" />
        </a>
      </div>
      {c.isBlocked && (
        <Alert variant="error">
          Bloqueado há {formatDuration(c.currentBlockTimeSeconds)}
          {c.blockReason?.label && ` — ${c.blockReason.label}`}
          {c.blockReason?.comment && `: ${c.blockReason.comment}`}
        </Alert>
      )}
      <Card>
        <CardContent className="pt-6">
          <dl className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Field label="Coluna">{c.columnName}</Field>
            <Field label="Lane">{c.laneName}</Field>
            <Field label="Workflow">{c.workflowName}</Field>
            <Field label="Tipo">{c.typeName}</Field>
            <Field label="Responsável">{c.ownerName}</Field>
            <Field label="Co-responsáveis">{c.coOwnerNames.length ? c.coOwnerNames.join(", ") : null}</Field>
            <Field label="Tamanho">{c.size != null ? formatNumber(c.size, 1) : null}</Field>
            <Field label="Tempo registado">{c.loggedTimeSeconds ? formatDuration(c.loggedTimeSeconds) : null}</Field>
            <Field label="Criado">{formatDateTime(c.createdAt)}</Field>
            <Field label="Início (1.º)">{formatDateTime(c.firstStartTime)}</Field>
            <Field label="Fim">{formatDateTime(c.endTime ?? c.lastEndTime)}</Field>
            <Field label="Prazo">{formatDateTime(c.deadline)}</Field>
            <Field label="Na posição atual desde">{formatDateTime(c.inCurrentPositionSince)}</Field>
            <Field label="Última modificação">{formatDateTime(c.lastModified)}</Field>
            <Field label="Arquivado">{c.archivedAt ? formatDateTime(c.archivedAt) : null}</Field>
            <Field label="Dados de">{formatDateTime(c.dataAsOf)}</Field>
          </dl>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Percurso no board</CardTitle>
          <CardDescription>Permanência em cada coluna, conforme as transições devolvidas pela API.</CardDescription>
        </CardHeader>
        <CardContent>
          {c.transitions.length === 0 ? (
            <p className="text-sm text-slate-500">Sem transições disponíveis para este cartão.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Coluna</TH>
                  <TH>Lane</TH>
                  <TH>Entrada</TH>
                  <TH>Saída</TH>
                  <TH className="text-right">Duração</TH>
                </TR>
              </THead>
              <TBody>
                {c.transitions.map((t, i) => (
                  <TR key={i}>
                    <TD>{t.columnName ?? t.column_id}</TD>
                    <TD>{t.laneName ?? "—"}</TD>
                    <TD>{formatDateTime(t.start)}</TD>
                    <TD>{t.end ? formatDateTime(t.end) : "atual"}</TD>
                    <TD className="text-right">{formatDuration(seconds(t.start, t.end))}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Alterações observadas</CardTitle>
          <CardDescription>
            Detetadas entre sincronizações{c.eventsSince ? `, recolhidas desde ${formatDateTime(c.eventsSince)}` : ""}. A hora é a da sincronização que observou a alteração.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {c.events.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma alteração observada.</p>
          ) : (
            <Table aria-label="Alterações observadas">
              <THead>
                <TR>
                  <TH>Quando</TH>
                  <TH>Alteração</TH>
                  <TH>De</TH>
                  <TH>Para</TH>
                </TR>
              </THead>
              <TBody>
                {c.events.map((e, i) => (
                  <TR key={i}>
                    <TD>{formatDateTime(e.occurredAt)}</TD>
                    <TD>{e.fieldLabel ?? e.field ?? e.type}</TD>
                    <TD>{e.fromLabel ?? (e.from == null ? "—" : String(e.from))}</TD>
                    <TD>{e.toLabel ?? (e.to == null ? "—" : String(e.to))}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
