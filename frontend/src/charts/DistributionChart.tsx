import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DistributionItem } from "@/api/dashboard";
import { ChartFrame } from "@/charts/ChartFrame";

interface Props {
  title: string;
  data: DistributionItem[];
  color?: string;
}

/** Barras horizontais: legível com nomes longos de colunas/responsáveis. */
export function DistributionChart({ title, data, color = "#0284c7" }: Props) {
  const height = Math.max(120, data.length * 32 + 40);
  return (
    <ChartFrame
      title={title}
      empty={data.length === 0}
      height={height}
      table={{ headers: ["Categoria", "Cartões"], rows: data.map((d) => [d.label, d.count]) }}
    >
      <ResponsiveContainer width="100%" height="100%" initialDimension={{ width: 400, height }}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          <XAxis type="number" allowDecimals={false} />
          <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => [v, "Cartões"]} />
          <Bar dataKey="count" fill={color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
