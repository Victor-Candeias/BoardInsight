import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Hours } from "@/api/hours";
import { ChartFrame } from "@/charts/ChartFrame";
import { colorAt } from "@/charts/palette";
import { formatHours } from "@/lib/format";

/** Horas por período, empilhadas por pessoa (eixo em horas; valores em HH:mm). */
export function HoursChart({ data }: { data: Hours }) {
  const people = data.byUser.filter((u) => u.seconds > 0);
  const key = (userId: number | null) => String(userId ?? "none");
  const points = data.buckets.map((b, i) => ({
    label: b.label,
    ...Object.fromEntries(people.map((p) => [key(p.userId), p.series[i] / 3600])),
  }));
  return (
    <ChartFrame
      title="Horas por período"
      empty={people.length === 0}
      height={300}
      table={{
        headers: ["Período", ...people.map((p) => p.name)],
        rows: data.buckets.map((b, i) => [b.label, ...people.map((p) => formatHours(p.series[i]))]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
        <BarChart data={points} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={(v: number) => formatHours(v * 3600)} width={56} />
          <Tooltip formatter={(v) => formatHours(Number(v) * 3600)} />
          <Legend />
          {people.map((p, i) => (
            <Bar key={key(p.userId)} dataKey={key(p.userId)} name={p.name} stackId="h" fill={colorAt(i)} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
