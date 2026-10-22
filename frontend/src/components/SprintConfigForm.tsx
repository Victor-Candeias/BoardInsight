import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { saveSprintConfig, type ExplicitSprint, type SprintConfig } from "@/api/sprints";
import { ErrorAlert } from "@/components/QueryState";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";

type Mode = "none" | "cadence" | "explicit";

export function SprintConfigForm({ boardId, config }: { boardId: number; config: SprintConfig }) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<Mode>(config.explicit.length ? "explicit" : config.cadence ? "cadence" : "none");
  const [start, setStart] = useState(config.cadence?.start ?? "");
  const [length, setLength] = useState(String(config.cadence?.lengthDays ?? 14));
  const [prefix, setPrefix] = useState(config.cadence?.namePrefix ?? "Sprint");
  const [rows, setRows] = useState<ExplicitSprint[]>(config.explicit.length ? config.explicit : [{ name: "", start: "", end: "" }]);

  const save = useMutation({
    mutationFn: () =>
      saveSprintConfig(boardId, {
        cadence: mode === "cadence" ? { start, lengthDays: Number(length), namePrefix: prefix || "Sprint" } : null,
        explicit: mode === "explicit" ? rows : [],
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sprints", boardId] }),
  });
  const setRow = (i: number, patch: Partial<ExplicitSprint>) => setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="space-y-1">
        <Label htmlFor="sprint-mode">Definição das sprints</Label>
        <Select id="sprint-mode" className="w-56" value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
          <option value="none">Sem sprints</option>
          <option value="cadence">Cadência fixa</option>
          <option value="explicit">Lista explícita</option>
        </Select>
      </div>
      {mode === "cadence" && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <Label htmlFor="cad-start">Início da 1.ª sprint</Label>
            <Input id="cad-start" type="date" required value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cad-length">Duração (dias)</Label>
            <Input id="cad-length" type="number" min={1} max={90} required className="w-28" value={length} onChange={(e) => setLength(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="cad-prefix">Prefixo do nome</Label>
            <Input id="cad-prefix" className="w-40" value={prefix} onChange={(e) => setPrefix(e.target.value)} />
          </div>
        </div>
      )}
      {mode === "explicit" && (
        <div className="space-y-2">
          {rows.map((row, i) => (
            <div key={i} className="flex flex-wrap items-end gap-2">
              <Input aria-label={`Nome da sprint ${i + 1}`} placeholder="Nome" required className="w-48" value={row.name} onChange={(e) => setRow(i, { name: e.target.value })} />
              <Input aria-label={`Início da sprint ${i + 1}`} type="date" required value={row.start} onChange={(e) => setRow(i, { start: e.target.value })} />
              <Input aria-label={`Fim da sprint ${i + 1}`} type="date" required value={row.end} onChange={(e) => setRow(i, { end: e.target.value })} />
              <Button type="button" variant="ghost" size="sm" onClick={() => setRows((r) => r.filter((_, j) => j !== i))} disabled={rows.length === 1}>
                Remover
              </Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => setRows((r) => [...r, { name: "", start: "", end: "" }])}>
            Adicionar sprint
          </Button>
        </div>
      )}
      <ErrorAlert error={save.error} />
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={save.isPending}>
          Guardar
        </Button>
        {save.isSuccess && <span className="text-sm text-emerald-700">Configuração guardada.</span>}
      </div>
    </form>
  );
}
