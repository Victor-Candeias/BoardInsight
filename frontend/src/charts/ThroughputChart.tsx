import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ThroughputPoint } from "@/api/delivery";
import { ChartFrame } from "@/charts/ChartFrame";
import { formatNumber } from "@/lib/format";

interface Props {
  data: ThroughputPoint[];
  measure: "count" | "size";
  average?: number;
}

export function ThroughputChart({ data, measure, average }: Props) {
  const name = measure === "count" ? "Cartões concluídos" : "Tamanho concluído";
  return (
    <ChartFrame
      title={`Throughput — ${name.toLowerCase()}`}
      empty={data.every((d) => !d.count)}
      height={300}
      table={{
        headers: ["Período", "Cartões", "Tamanho", "Parcial"],
        rows: data.map((d) => [d.label, d.count, formatNumber(d.size, 1), d.partial ? "sim" : "não"]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 600, height: 300 }}>
        <BarChart data={data} margin={{ right: 16 }}>
          <CartesianGrid vertical={false} strokeDasharray="3 3" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={measure === "size"} />
          <Tooltip formatter={(v) => [formatNumber(Number(v), 1), name]} />
          <Bar dataKey={measure} name={name}>
            {data.map((d) => (
              <Cell key={d.bucket} fill={d.partial ? "#bae6fd" : "#0284c7"} />
            ))}
          </Bar>
          {measure === "count" && average !== undefined && (
            <ReferenceLine y={average} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: `média ${formatNumber(average, 1)}`, position: "insideTopRight", fontSize: 12 }} />
          )}
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
