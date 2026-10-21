import type { PeriodQuery } from "@/api/dashboard";
import { Input, Label, Select } from "@/components/ui/input";

interface Props {
  query: PeriodQuery;
  setFilter: (key: string, value: string | null) => void;
  /** Período efetivo devolvido pela API (mostrado quando o URL não o define). */
  effective?: { from: string; to: string };
}

export function PeriodControls({ query, setFilter, effective }: Props) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <Label htmlFor="p-from">De</Label>
        <Input id="p-from" type="date" value={query.from ?? effective?.from ?? ""} onChange={(e) => setFilter("from", e.target.value || null)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="p-to">Até</Label>
        <Input id="p-to" type="date" value={query.to ?? effective?.to ?? ""} onChange={(e) => setFilter("to", e.target.value || null)} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="p-granularity">Agrupar por</Label>
        <Select id="p-granularity" className="w-32" value={query.granularity ?? "week"} onChange={(e) => setFilter("granularity", e.target.value)}>
          <option value="day">Dia</option>
          <option value="week">Semana</option>
          <option value="month">Mês</option>
        </Select>
      </div>
    </div>
  );
}
