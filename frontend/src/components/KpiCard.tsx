import { Link } from "react-router";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatNumber } from "@/lib/format";

interface Props {
  label: string;
  value: number | null | undefined;
  /** Texto apresentado em vez do número formatado (ex.: horas em HH:mm). */
  display?: string;
  hint?: string;
  to?: string;
  tone?: "default" | "warning" | "danger";
  digits?: number;
}

const TONES = { default: "text-slate-900", warning: "text-amber-700", danger: "text-red-700" };

export function KpiCard({ label, value, display, hint, to, tone = "default", digits = 0 }: Props) {
  const body = (
    <Card className={cn("h-full", to && "transition-colors hover:border-sky-300")}>
      <CardContent className="space-y-1 pt-4">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
        <div className={cn("text-2xl font-semibold", value ? TONES[tone] : TONES.default)}>{display ?? formatNumber(value, digits)}</div>
        {hint && <div className="text-xs text-slate-500">{hint}</div>}
      </CardContent>
    </Card>
  );
  return to ? (
    <Link to={to} aria-label={`${label}: ${formatNumber(value ?? 0, digits)}`}>
      {body}
    </Link>
  ) : (
    body
  );
}
