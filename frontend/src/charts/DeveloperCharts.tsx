import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Developers } from "@/api/delivery";
import { ChartFrame } from "@/charts/ChartFrame";
import { colorAt } from "@/charts/palette";

export function OpenWorkChart({ data }: { data: Developers["developers"] }) {
  const rows = data.filter((d) => d.open > 0);
  const height = Math.max(140, rows.length * 34 + 60);
  return (
    <ChartFrame
      title="Trabalho aberto por pessoa"
      empty={rows.length === 0}
      height={height}
      table={{ headers: ["Pessoa", "Backlog", "A fazer", "Em curso"], rows: rows.map((d) => [d.name, d.backlog, d.todo, d.inProgress]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 500, height }}>
        <BarChart data={rows} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Bar dataKey="backlog" name="Backlog" stackId="s" fill="#cbd5e1" />
          <Bar dataKey="todo" name="A fazer" stackId="s" fill="#7dd3fc" />
          <Bar dataKey="inProgress" name="Em curso" stackId="s" fill="#0284c7" />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function CompletedByPersonChart({ data }: { data: Developers }) {
  const people = data.developers.filter((d) => d.completed > 0);
  const points = data.buckets.map((b, i) => ({
    label: b.label,
    ...Object.fromEntries(people.map((p) => [String(p.userId), p.completedSeries[i]])),
  }));
  return (
    <ChartFrame
      title="Concluídos por pessoa e período"
      empty={people.length === 0}
      height={300}
      table={{ headers: ["Período", ...people.map((p) => p.name)], rows: data.buckets.map((b, i) => [b.label, ...people.map((p) => p.completedSeries[i])]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
        <LineChart data={points} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          {people.map((p, i) => (
            <Line key={String(p.userId)} dataKey={String(p.userId)} name={p.name} stroke={colorAt(i)} strokeWidth={2} dot={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
