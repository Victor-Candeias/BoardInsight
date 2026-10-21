import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimelinePoint } from "@/api/dashboard";
import { ChartFrame } from "@/charts/ChartFrame";

export function TimelineChart({ title, data }: { title: string; data: TimelinePoint[] }) {
  return (
    <ChartFrame
      title={title}
      empty={data.every((d) => !d.created && !d.completed)}
      height={280}
      table={{ headers: ["Período", "Criados", "Concluídos"], rows: data.map((d) => [d.label, d.created, d.completed]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 280 }}>
        <BarChart data={data} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="created" name="Criados" fill="#94a3b8" />
          <Bar dataKey="completed" name="Concluídos" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
