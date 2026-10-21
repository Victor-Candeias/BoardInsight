import { useNavigate, useParams } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { boardsKey, deleteBoard, getBoard, listSyncRuns, testConnection } from "@/api/boards";
import { ConnectionChecks } from "@/components/ConnectionChecks";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { formatDateTime, formatNumber } from "@/lib/format";
import { SyncBadge } from "@/pages/BoardsPage";

export function BoardDetailPage() {
  const boardId = Number(useParams().boardId);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const board = useQuery({ queryKey: ["board", boardId], queryFn: () => getBoard(boardId) });
  const runs = useQuery({ queryKey: ["sync-runs", boardId], queryFn: () => listSyncRuns(boardId) });
  const test = useMutation({ mutationFn: () => testConnection(boardId) });
  const remove = useMutation({
    mutationFn: () => deleteBoard(boardId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: boardsKey });
      navigate("/boards");
    },
  });

  if (board.isLoading) return <Loading />;
  if (board.error || !board.data) return <ErrorAlert error={board.error} />;
  const b = board.data;

  const confirmRemove = () => {
    if (window.confirm(`Remover o board ${b.boardId} e todos os dados sincronizados localmente?`)) remove.mutate();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">{b.name || `Board ${b.boardId}`}</h1>
          <p className="text-sm text-slate-500">
            ID {b.boardId} · workspace {b.workspaceId ?? "—"} · {formatNumber(b.cardCount)} cartões ativos ·{" "}
            <SyncBadge board={b} />
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => test.mutate()} disabled={test.isPending}>
            {test.isPending ? "A testar…" : "Testar ligação"}
          </Button>
          <Button variant="destructive" onClick={confirmRemove} disabled={remove.isPending}>
            Remover
          </Button>
        </div>
      </div>
      <ErrorAlert error={test.error ?? remove.error} />
      {b.lastSyncError && (
        <Alert variant="error">
          Última sincronização falhou: {b.lastSyncError.message} ({b.lastSyncError.code})
        </Alert>
      )}
      {b.metadataWarnings.length > 0 && <Alert variant="warning">{b.metadataWarnings.join("; ")}</Alert>}
      {test.data && (
        <Card>
          <CardContent className="pt-6">
            <ConnectionChecks result={test.data} />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Mapeamento de colunas</CardTitle>
          <CardDescription>
            Estado normalizado derivado da secção Businessmap de cada coluna (só leitura). As colunas de cycle time vêm
            da configuração do board.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {b.columns.length === 0 ? (
            <p className="text-sm text-slate-500">Estrutura ainda não sincronizada.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>Workflow</TH>
                  <TH>Coluna</TH>
                  <TH>Secção</TH>
                  <TH>Estado</TH>
                  <TH>Cycle time</TH>
                  <TH className="text-right">Limite WIP</TH>
                </TR>
              </THead>
              <TBody>
                {b.columns.map((c) => (
                  <TR key={c.columnId}>
                    <TD>{c.workflowName ?? c.workflowId}</TD>
                    <TD>
                      {c.parentName && <span className="text-slate-400">{c.parentName} › </span>}
                      {c.name}
                    </TD>
                    <TD>{c.sectionName}</TD>
                    <TD>{c.statusLabel}</TD>
                    <TD>{c.cycleTime ? <Badge variant="info">Sim</Badge> : "—"}</TD>
                    <TD className="text-right">{c.wipLimit || "—"}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Lanes e tipos de cartão</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 text-sm">
          {b.lanes.map((l) => (
            <Badge key={`l${l.laneId}`}>Lane: {l.name}</Badge>
          ))}
          {b.cardTypes.map((t) => (
            <Badge key={`t${t.typeId}`} variant="info">
              {t.name}
            </Badge>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Histórico de sincronização</CardTitle>
        </CardHeader>
        <CardContent>
          <ErrorAlert error={runs.error} />
          {runs.data?.length === 0 && <p className="text-sm text-slate-500">Sem sincronizações registadas.</p>}
          {!!runs.data?.length && (
            <Table>
              <THead>
                <TR>
                  <TH>Início</TH>
                  <TH>Origem</TH>
                  <TH>Resultado</TH>
                  <TH className="text-right">Duração</TH>
                  <TH className="text-right">Cartões</TH>
                  <TH>Erro</TH>
                </TR>
              </THead>
              <TBody>
                {runs.data.map((r) => (
                  <TR key={r.id}>
                    <TD>{formatDateTime(r.startedAt)}</TD>
                    <TD>{r.trigger === "manual" ? "Manual" : "Agendada"}</TD>
                    <TD>
                      <Badge variant={r.status === "success" ? "success" : r.status === "error" ? "danger" : "default"}>
                        {r.status === "success" ? "Sucesso" : r.status === "error" ? "Erro" : "A decorrer"}
                      </Badge>
                    </TD>
                    <TD className="text-right">{r.durationMs != null ? `${formatNumber(r.durationMs / 1000, 1)} s` : "—"}</TD>
                    <TD className="text-right">{formatNumber(r.stats?.activeCards as number | undefined)}</TD>
                    <TD className="text-slate-500">{r.error?.message ?? ""}</TD>
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
