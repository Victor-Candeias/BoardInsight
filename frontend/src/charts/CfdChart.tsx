import { Area, AreaChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Cfd } from "@/api/delivery";
import { ChartFrame } from "@/charts/ChartFrame";
import { colorAt } from "@/charts/palette";
import { formatDate } from "@/lib/format";

const STATUS_COLORS: Record<string, string> = { backlog: "#94a3b8", todo: "#0284c7", in_progress: "#f59e0b", done: "#16a34a" };

/** Áreas empilhadas: a última etapa do fluxo (concluído / última coluna) fica em baixo. */
export function CfdChart({ cfd }: { cfd: Cfd }) {
  const data = cfd.days.map((d) => ({ label: formatDate(d.date), ...d.counts }));
  const color = (key: string, i: number) => (cfd.group === "status" ? (STATUS_COLORS[key] ?? colorAt(i)) : colorAt(i));
  const stacked = cfd.series.map((s, i) => ({ ...s, color: color(s.key, i) })).reverse();
  return (
    <ChartFrame
      title={`Cumulative Flow Diagram por ${cfd.group === "status" ? "estado" : "coluna"}`}
      empty={!cfd.available}
      height={380}
      table={{
        headers: ["Dia", ...cfd.series.map((s) => s.label)],
        rows: cfd.days.map((d) => [formatDate(d.date), ...cfd.series.map((s) => d.counts[s.key] ?? 0)]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 800, height: 380 }}>
        <AreaChart data={data} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} minTickGap={16} />
          <YAxis allowDecimals={false} />
          <Tooltip />
          <Legend />
          {stacked.map((s) => (
            <Area key={s.key} type="stepAfter" dataKey={s.key} name={s.label} stackId="cfd" stroke={s.color} fill={s.color} fillOpacity={0.7} isAnimationActive={false} />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
