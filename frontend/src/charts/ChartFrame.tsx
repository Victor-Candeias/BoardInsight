import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface Props {
  title: string;
  /** Tabela acessível com os mesmos dados do gráfico (leitores de ecrã e testes). */
  table: { headers: string[]; rows: (string | number)[][] };
  empty?: boolean;
  height?: number;
  children: ReactNode;
}

export function ChartFrame({ title, table, empty, height = 260, children }: Props) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {empty ? (
          <p className="py-8 text-center text-sm text-slate-500">Sem dados para os filtros escolhidos.</p>
        ) : (
          <div style={{ height }} aria-hidden="true">
            {children}
          </div>
        )}
        <table className="sr-only">
          <caption>{title}</caption>
          <thead>
            <tr>
              {table.headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((r, i) => (
              <tr key={i}>
                {r.map((v, j) => (
                  <td key={j}>{v}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
