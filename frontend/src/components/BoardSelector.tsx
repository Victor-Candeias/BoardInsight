import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { boardsKey, listBoards } from "@/api/boards";
import { Select } from "@/components/ui/input";
import { useActiveBoard } from "@/hooks/useActiveBoard";

export function BoardSelector() {
  const [activeId, setActiveId] = useActiveBoard();
  const { data: boards, isFetching } = useQuery({ queryKey: boardsKey, queryFn: () => listBoards() });

  // Mantém a seleção válida: escolhe o primeiro board se o ativo deixou de existir.
  useEffect(() => {
    if (!boards || isFetching) return;
    if (activeId !== null && boards.some((b) => b.boardId === activeId)) return;
    setActiveId(boards[0]?.boardId ?? null);
  }, [boards, isFetching, activeId, setActiveId]);

  if (!boards?.length) return <span className="text-sm text-slate-500">Nenhum board configurado</span>;

  return (
    <Select
      aria-label="Board ativo"
      className="w-72"
      value={activeId ?? ""}
      onChange={(e) => setActiveId(Number(e.target.value))}
    >
      {boards.map((b) => (
        <option key={b.boardId} value={b.boardId}>
          {b.name || `Board ${b.boardId}`} (#{b.boardId})
        </option>
      ))}
    </Select>
  );
}
