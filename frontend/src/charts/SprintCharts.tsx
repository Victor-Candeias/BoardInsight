import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { SprintDetail, SprintRow } from "@/api/sprints";
import { ChartFrame } from "@/charts/ChartFrame";
import { formatDate, formatNumber } from "@/lib/format";

export function VelocityChart({ sprints }: { sprints: SprintRow[] }) {
  return (
    <ChartFrame
      title="Velocity por sprint"
      empty={sprints.length === 0}
      table={{
        headers: ["Sprint", "Concluídos", "Tamanho", "Compromisso", "Compromisso concluído"],
        rows: sprints.map((s) => [s.name, s.completed, s.completedSize, s.committed ?? "—", s.committedDone ?? "—"]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 260 }}>
        <BarChart data={sprints}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="committed" name="Compromisso" fill="#94a3b8" />
          <Bar dataKey="completed" name="Concluídos" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function BurndownChart({ sprint }: { sprint: SprintDetail }) {
  const data = sprint.burndown.map((d) => ({ ...d, label: formatDate(d.date) }));
  return (
    <ChartFrame
      title={`Burndown — ${sprint.name}`}
      empty={!sprint.commitmentAvailable}
      table={{
        headers: ["Dia", "Por concluir", "Tamanho por concluir", "Ideal"],
        rows: data.map((d) => [d.label, d.remaining ?? "sem snapshot", d.remainingSize ?? "—", formatNumber(d.ideal, 1)]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 260 }}>
        <LineChart data={data} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Line dataKey="ideal" name="Ideal" stroke="#94a3b8" strokeDasharray="4 4" dot={false} />
          <Line dataKey="remaining" name="Por concluir" stroke="#0284c7" strokeWidth={2} connectNulls type="stepAfter" />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
