import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getFilterOptions, type CardQuery, type Option } from "@/api/cards";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";

interface Props {
  boardId: number;
  query: CardQuery;
  setFilter: (key: string, value: string | null) => void;
  setFilters: (updates: Record<string, string | null>) => void;
  clear: () => void;
  /** Esconde filtros que não fazem sentido numa página (ex.: estado do cartão). */
  hide?: string[];
}

function OptionSelect({
  id,
  label,
  value,
  options,
  onChange,
  allLabel = "Todos",
}: {
  id: string;
  label: string;
  value?: string;
  options: Option[];
  onChange: (v: string | null) => void;
  allLabel?: string;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id}>{label}</Label>
      <Select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)} className="w-44">
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={String(o.value)} value={String(o.value)}>
            {o.label}
          </option>
        ))}
      </Select>
    </div>
  );
}

export function CardFiltersBar({ boardId, query, setFilter, setFilters, clear, hide = [] }: Props) {
  const { data: options } = useQuery({ queryKey: ["filter-options", boardId], queryFn: () => getFilterOptions(boardId) });
  const [text, setText] = useState(query.q ?? "");

  useEffect(() => setText(query.q ?? ""), [query.q]);
  useEffect(() => {
    const t = setTimeout(() => {
      if ((query.q ?? "") !== text) setFilter("q", text.trim() || null);
    }, 300);
    return () => clearTimeout(t);
  }, [text, query.q, setFilter]);

  const shown = (key: string) => !hide.includes(key);
  const owners = [{ value: "none", label: "Sem responsável" }, ...(options?.owners ?? [])];
  const ownerValue = query.unassigned === "true" ? "none" : query.ownerUserId;

  return (
    <div className="flex flex-wrap items-end gap-3">
      {shown("q") && (
        <div className="space-y-1">
          <Label htmlFor="f-q">Pesquisa</Label>
          <Input id="f-q" className="w-56" placeholder="Título ou ID" value={text} onChange={(e) => setText(e.target.value)} />
        </div>
      )}
      {shown("state") && (
        <OptionSelect
          id="f-state"
          label="Cartões"
          allLabel="Ativos"
          value={query.state}
          options={[
            { value: "archived", label: "Arquivados" },
            { value: "all", label: "Ativos e arquivados" },
          ]}
          onChange={(v) => setFilter("state", v)}
        />
      )}
      {shown("status") && (
        <OptionSelect id="f-status" label="Estado" value={query.status} options={options?.statuses ?? []} onChange={(v) => setFilter("status", v)} />
      )}
      {shown("columnId") && (
        <OptionSelect id="f-column" label="Coluna" value={query.columnId} options={options?.columns ?? []} onChange={(v) => setFilter("columnId", v)} />
      )}
      {shown("laneId") && (
        <OptionSelect id="f-lane" label="Lane" value={query.laneId} options={options?.lanes ?? []} onChange={(v) => setFilter("laneId", v)} />
      )}
      {shown("ownerUserId") && (
        <OptionSelect
          id="f-owner"
          label="Responsável"
          value={ownerValue}
          options={owners}
          onChange={(v) => setFilters({ unassigned: v === "none" ? "true" : null, ownerUserId: v === "none" ? null : v })}
        />
      )}
      {shown("typeId") && (
        <OptionSelect id="f-type" label="Tipo" value={query.typeId} options={options?.types ?? []} onChange={(v) => setFilter("typeId", v)} />
      )}
      {shown("priority") && (
        <OptionSelect id="f-priority" label="Prioridade" allLabel="Todas" value={query.priority} options={options?.priorities ?? []} onChange={(v) => setFilter("priority", v)} />
      )}
      {shown("createdFrom") && (
        <div className="space-y-1">
          <Label htmlFor="f-created-from">Criado de</Label>
          <Input id="f-created-from" type="date" value={query.createdFrom ?? ""} onChange={(e) => setFilter("createdFrom", e.target.value || null)} />
        </div>
      )}
      {shown("createdTo") && (
        <div className="space-y-1">
          <Label htmlFor="f-created-to">até</Label>
          <Input id="f-created-to" type="date" value={query.createdTo ?? ""} onChange={(e) => setFilter("createdTo", e.target.value || null)} />
        </div>
      )}
      <div className="flex items-center gap-3 pb-2 text-sm">
        {shown("open") && (
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={query.open === "true"} onChange={(e) => setFilter("open", e.target.checked ? "true" : null)} />
            Só abertos
          </label>
        )}
        {shown("blocked") && (
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={query.blocked === "true"} onChange={(e) => setFilter("blocked", e.target.checked ? "true" : null)} />
            Bloqueados
          </label>
        )}
        {shown("overdue") && (
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={query.overdue === "true"} onChange={(e) => setFilter("overdue", e.target.checked ? "true" : null)} />
            Em atraso
          </label>
        )}
        {shown("dueSoon") && (
          <label className="flex items-center gap-1">
            <input type="checkbox" checked={query.dueSoon === "true"} onChange={(e) => setFilter("dueSoon", e.target.checked ? "true" : null)} />
            Prazo ≤ 7 dias
          </label>
        )}
      </div>
      <Button variant="ghost" size="sm" onClick={clear}>
        Limpar filtros
      </Button>
    </div>
  );
}
