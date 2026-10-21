import { useMemo } from "react";
import { Link } from "react-router";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";
import { listCards, type Card } from "@/api/cards";
import { CardFiltersBar } from "@/components/CardFiltersBar";
import { CardFlags, PriorityBadge, StatusBadge } from "@/components/CardBadges";
import { NoBoard } from "@/components/NoBoard";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Button } from "@/components/ui/button";
import { Card as Panel, CardContent } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { useCardFilters } from "@/hooks/useCardFilters";
import { formatDate, formatDateTime, formatNumber } from "@/lib/format";

const PAGE_SIZES = [25, 50, 100, 200];
const EXTRA_KEYS = ["sort", "page", "pageSize"];
const col = createColumnHelper<Card>();

const columns = [
  col.accessor("cardId", {
    header: "ID",
    cell: ({ row }) => (
      <Link to={`/cards/${row.original.cardId}`} className="font-mono text-sky-700 hover:underline">
        {row.original.customId || row.original.cardId}
      </Link>
    ),
  }),
  col.accessor("title", {
    header: "Título",
    cell: ({ row }) => (
      <div className="space-y-1">
        <div className="flex items-center gap-1">
          <Link to={`/cards/${row.original.cardId}`} className="hover:underline">
            {row.original.title || "(sem título)"}
          </Link>
          <a href={row.original.url} target="_blank" rel="noreferrer" aria-label="Abrir no Businessmap" className="text-slate-400 hover:text-slate-700">
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>
        <CardFlags card={row.original} />
      </div>
    ),
  }),
  col.accessor("status", { header: "Estado", cell: ({ row }) => <StatusBadge card={row.original} /> }),
  col.display({
    id: "position",
    header: "Coluna / Lane",
    cell: ({ row }) => (
      <div>
        <div>{row.original.columnName ?? "—"}</div>
        <div className="text-xs text-slate-500">{row.original.laneName}</div>
      </div>
    ),
  }),
  col.display({ id: "owner", header: "Responsável", cell: ({ row }) => row.original.ownerName ?? <span className="text-slate-400">—</span> }),
  col.accessor("priority", { header: "Prioridade", cell: ({ row }) => <PriorityBadge card={row.original} /> }),
  col.display({ id: "type", header: "Tipo", cell: ({ row }) => row.original.typeName ?? "—" }),
  col.accessor("size", { header: "Tamanho", cell: ({ getValue }) => formatNumber(getValue(), 1) }),
  col.accessor("deadline", { header: "Prazo", cell: ({ getValue }) => formatDate(getValue()) }),
  col.accessor("createdAt", { header: "Criado", cell: ({ getValue }) => formatDate(getValue()) }),
  col.accessor("lastModified", { header: "Modificado", cell: ({ getValue }) => formatDateTime(getValue()) }),
];

const SORTABLE = new Set(["cardId", "title", "status", "priority", "size", "deadline", "createdAt", "lastModified"]);

export function CardsPage() {
  const [boardId] = useActiveBoard();
  const { query, setFilter, setFilters, clear } = useCardFilters(EXTRA_KEYS);
  const page = Number(query.page ?? 1);
  const pageSize = Number(query.pageSize ?? 50);
  const sorting: SortingState = useMemo(() => {
    const s = query.sort ?? "-lastModified";
    return [{ id: s.replace(/^-/, ""), desc: s.startsWith("-") }];
  }, [query.sort]);

  const cards = useQuery({
    queryKey: ["cards", boardId, query],
    queryFn: () => listCards(boardId!, query),
    enabled: boardId !== null,
    placeholderData: keepPreviousData,
  });

  const table = useReactTable({
    data: cards.data?.items ?? [],
    columns,
    state: { sorting },
    manualSorting: true,
    manualPagination: true,
    enableSortingRemoval: false,
    getCoreRowModel: getCoreRowModel(),
    getRowId: (c) => String(c.cardId),
  });

  if (boardId === null) return <NoBoard />;

  const total = cards.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / pageSize));

  const toggleSort = (id: string) => {
    const current = sorting[0];
    const desc = current?.id === id ? !current.desc : id !== "title";
    setFilter("sort", `${desc ? "-" : ""}${id}`);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Cartões</h1>
        {cards.data && (
          <span className="text-sm text-slate-500">
            {formatNumber(total)} cartões · dados de {formatDateTime(cards.data.dataAsOf)}
          </span>
        )}
      </div>
      <Panel>
        <CardContent className="pt-6">
          <CardFiltersBar boardId={boardId} query={query} setFilter={setFilter} setFilters={setFilters} clear={clear} />
        </CardContent>
      </Panel>
      <ErrorAlert error={cards.error} />
      {cards.isLoading ? (
        <Loading />
      ) : (
        <Panel>
          <CardContent className="overflow-x-auto pt-6">
            <Table>
              <THead>
                {table.getHeaderGroups().map((hg) => (
                  <TR key={hg.id}>
                    {hg.headers.map((h) => {
                      const sortable = SORTABLE.has(h.column.id);
                      const sorted = sorting[0]?.id === h.column.id ? (sorting[0].desc ? "desc" : "asc") : null;
                      return (
                        <TH key={h.id} aria-sort={sorted ? (sorted === "asc" ? "ascending" : "descending") : undefined}>
                          {sortable ? (
                            <button type="button" className="inline-flex items-center gap-1" onClick={() => toggleSort(h.column.id)}>
                              {flexRender(h.column.columnDef.header, h.getContext())}
                              {sorted === "asc" && <ArrowUp className="h-3 w-3" />}
                              {sorted === "desc" && <ArrowDown className="h-3 w-3" />}
                            </button>
                          ) : (
                            flexRender(h.column.columnDef.header, h.getContext())
                          )}
                        </TH>
                      );
                    })}
                  </TR>
                ))}
              </THead>
              <TBody>
                {table.getRowModel().rows.length === 0 && (
                  <TR>
                    <TD colSpan={columns.length} className="py-8 text-center text-slate-500">
                      Nenhum cartão corresponde aos filtros.
                    </TD>
                  </TR>
                )}
                {table.getRowModel().rows.map((row) => (
                  <TR key={row.id}>
                    {row.getVisibleCells().map((cell) => (
                      <TD key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TD>
                    ))}
                  </TR>
                ))}
              </TBody>
            </Table>
            <div className="mt-4 flex items-center justify-between text-sm">
              <div className="flex items-center gap-2">
                <span>Por página</span>
                <Select aria-label="Cartões por página" className="w-20" value={pageSize} onChange={(e) => setFilter("pageSize", e.target.value)}>
                  {PAGE_SIZES.map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setFilter("page", String(page - 1))}>
                  Anterior
                </Button>
                <span>
                  Página {page} de {pages}
                </span>
                <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setFilter("page", String(page + 1))}>
                  Seguinte
                </Button>
              </div>
            </div>
          </CardContent>
        </Panel>
      )}
    </div>
  );
}
