import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Blockers, Quality } from "@/api/delivery";
import { ChartFrame } from "@/charts/ChartFrame";

export function BlockHistoryChart({ series }: { series: Blockers["history"]["series"] }) {
  return (
    <ChartFrame
      title="Bloqueios observados por intervalo"
      empty={series.every((s) => !s.started && !s.resolved)}
      table={{ headers: ["Período", "Bloqueados", "Desbloqueados"], rows: series.map((s) => [s.label, s.started, s.resolved]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 260 }}>
        <BarChart data={series}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          <Bar dataKey="started" name="Bloqueados" fill="#dc2626" />
          <Bar dataKey="resolved" name="Desbloqueados" fill="#16a34a" />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function ReopenChart({ series }: { series: Quality["series"] }) {
  return (
    <ChartFrame
      title="Reaberturas por intervalo"
      empty={series.every((s) => !s.reopens)}
      table={{ headers: ["Período", "Reaberturas"], rows: series.map((s) => [s.label, s.reopens]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 260 }}>
        <BarChart data={series}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Bar dataKey="reopens" name="Reaberturas" fill="#ea580c" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
