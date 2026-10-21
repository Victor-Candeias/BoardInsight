import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { addBoard, boardsKey, listBoards, testConnection, updateBoard, type BoardSummary } from "@/api/boards";
import { ConnectionChecks } from "@/components/ConnectionChecks";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { formatDateTime, formatNumber } from "@/lib/format";

export function SyncBadge({ board }: { board: Pick<BoardSummary, "lastSyncStatus" | "stale" | "lastSuccessfulSyncAt"> }) {
  if (board.lastSyncStatus === "error") return <Badge variant="danger">Erro na última sync</Badge>;
  if (!board.lastSuccessfulSyncAt) return <Badge>Por sincronizar</Badge>;
  if (board.stale) return <Badge variant="warning">Desatualizado</Badge>;
  return <Badge variant="success">Atualizado</Badge>;
}

function AddBoardCard() {
  const queryClient = useQueryClient();
  const [, setActiveId] = useActiveBoard();
  const [value, setValue] = useState("");
  const boardId = Number(value);
  const valid = Number.isInteger(boardId) && boardId > 0;

  const test = useMutation({ mutationFn: () => testConnection(boardId) });
  const add = useMutation({
    mutationFn: () => addBoard(boardId),
    onSuccess: async (board) => {
      setValue("");
      test.reset();
      await queryClient.invalidateQueries({ queryKey: boardsKey });
      setActiveId(board.boardId);
    },
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) add.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Adicionar board</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form onSubmit={submit} className="flex items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor="board-id">ID do board</Label>
            <Input
              id="board-id"
              inputMode="numeric"
              className="w-40"
              value={value}
              onChange={(e) => {
                setValue(e.target.value.replace(/\D/g, ""));
                test.reset();
                add.reset();
              }}
              placeholder="ex.: 96"
            />
          </div>
          <Button type="button" variant="outline" disabled={!valid || test.isPending} onClick={() => test.mutate()}>
            {test.isPending ? "A testar…" : "Testar ligação"}
          </Button>
          <Button type="submit" disabled={!valid || add.isPending}>
            {add.isPending ? "A adicionar…" : "Adicionar"}
          </Button>
        </form>
        <ErrorAlert error={test.error ?? add.error} />
        {test.data && <ConnectionChecks result={test.data} />}
      </CardContent>
    </Card>
  );
}

export function BoardsPage() {
  const queryClient = useQueryClient();
  const [activeId, setActiveId] = useActiveBoard();
  const [search, setSearch] = useState("");
  const boards = useQuery({ queryKey: [...boardsKey, search], queryFn: () => listBoards(search) });
  const toggle = useMutation({
    mutationFn: (b: BoardSummary) => updateBoard(b.boardId, { enabled: !b.enabled }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: boardsKey }),
  });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Boards</h1>
      <AddBoardCard />
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle>Boards configurados</CardTitle>
          <Input
            aria-label="Pesquisar boards"
            placeholder="Pesquisar por nome ou ID"
            className="w-64"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </CardHeader>
        <CardContent>
          <ErrorAlert error={boards.error ?? toggle.error} />
          {boards.isLoading ? (
            <Loading />
          ) : boards.data?.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum board encontrado.</p>
          ) : (
            <Table>
              <THead>
                <TR>
                  <TH>ID</TH>
                  <TH>Nome</TH>
                  <TH>Estado</TH>
                  <TH>Última sync com sucesso</TH>
                  <TH className="text-right">Cartões ativos</TH>
                  <TH>Sync automática</TH>
                  <TH />
                </TR>
              </THead>
              <TBody>
                {boards.data?.map((b) => (
                  <TR key={b.boardId}>
                    <TD>{b.boardId}</TD>
                    <TD>
                      <Link to={`/boards/${b.boardId}`} className="font-medium text-sky-700 hover:underline">
                        {b.name || `Board ${b.boardId}`}
                      </Link>
                      {b.isArchived && <Badge className="ml-2">Arquivado</Badge>}
                    </TD>
                    <TD>
                      <SyncBadge board={b} />
                    </TD>
                    <TD>{formatDateTime(b.lastSuccessfulSyncAt)}</TD>
                    <TD className="text-right">{formatNumber(b.cardCount)}</TD>
                    <TD>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={b.enabled}
                          onChange={() => toggle.mutate(b)}
                          aria-label={`Sync automática do board ${b.boardId}`}
                        />
                        {b.enabled ? "Ativa" : "Pausada"}
                      </label>
                    </TD>
                    <TD className="text-right">
                      {activeId === b.boardId ? (
                        <Badge variant="info">Board ativo</Badge>
                      ) : (
                        <Button size="sm" variant="ghost" onClick={() => setActiveId(b.boardId)}>
                          Selecionar
                        </Button>
                      )}
                    </TD>
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
