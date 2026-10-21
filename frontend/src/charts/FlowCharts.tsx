import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Flow, MetricSummary } from "@/api/delivery";
import { ChartFrame } from "@/charts/ChartFrame";
import { formatDate, formatNumber } from "@/lib/format";

/** Dispersão: cada cartão concluído (data de fim × dias), com linhas P50/P85. */
export function TimeScatterChart({ flow, metric }: { flow: Flow; metric: "cycleDays" | "leadDays" }) {
  const summary: MetricSummary = metric === "cycleDays" ? flow.cycleTime : flow.leadTime;
  const name = metric === "cycleDays" ? "Cycle time" : "Lead time";
  const data = flow.points
    .filter((p) => p[metric] !== null)
    .map((p) => ({ x: new Date(p.endTime).getTime(), y: p[metric], id: p.customId || p.cardId, title: p.title }));
  return (
    <ChartFrame
      title={`${name} por cartão concluído (dias)`}
      empty={data.length === 0}
      height={300}
      table={{ headers: ["Cartão", "Fim", "Dias"], rows: data.map((d) => [String(d.id), formatDate(new Date(d.x).toISOString()), formatNumber(d.y, 1)]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
        <ScatterChart margin={{ right: 24 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" domain={["dataMin", "dataMax"]} tickFormatter={(v) => formatDate(new Date(v).toISOString())} tick={{ fontSize: 12 }} />
          <YAxis type="number" dataKey="y" name="Dias" />
          <Tooltip
            formatter={(v, n) => (n === "x" ? formatDate(new Date(Number(v)).toISOString()) : formatNumber(Number(v), 1))}
            labelFormatter={() => ""}
          />
          <Scatter data={data} fill="#0284c7" name={name} />
          {summary.available && (
            <>
              <ReferenceLine y={summary.p50} stroke="#16a34a" strokeDasharray="4 4" label={{ value: "P50", position: "right", fontSize: 11 }} />
              <ReferenceLine y={summary.p85} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: "P85", position: "right", fontSize: 11 }} />
            </>
          )}
        </ScatterChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}

export function CycleTrendChart({ trend }: { trend: Flow["trend"] }) {
  return (
    <ChartFrame
      title="Evolução do cycle time (dias)"
      empty={trend.every((t) => t.cycleP50 === null)}
      height={260}
      table={{
        headers: ["Período", "Concluídos", "Cycle P50", "Cycle P85", "Lead P50"],
        rows: trend.map((t) => [t.label, t.count, formatNumber(t.cycleP50, 1), formatNumber(t.cycleP85, 1), formatNumber(t.leadP50, 1)]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 260 }}>
        <LineChart data={trend} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis />
          <Tooltip formatter={(v) => formatNumber(Number(v), 1)} />
          <Legend />
          <Line dataKey="cycleP50" name="Cycle P50" stroke="#16a34a" connectNulls strokeWidth={2} />
          <Line dataKey="cycleP85" name="Cycle P85" stroke="#f59e0b" connectNulls strokeWidth={2} />
          <Line dataKey="leadP50" name="Lead P50" stroke="#64748b" connectNulls strokeDasharray="4 4" />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
