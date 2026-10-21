import { CheckCircle2, XCircle, MinusCircle } from "lucide-react";
import type { ConnectionResult } from "@/api/boards";

export function ConnectionChecks({ result }: { result: ConnectionResult }) {
  return (
    <div className="space-y-2 text-sm">
      <p className={result.ok ? "font-medium text-emerald-700" : "font-medium text-red-700"}>
        {result.ok ? "Ligação OK" : "Sem acesso de leitura suficiente"}
        {result.boardName && ` — ${result.boardName}`}
      </p>
      <ul className="space-y-1">
        {result.checks.map((c) => (
          <li key={c.name} className="flex items-start gap-2">
            {c.ok ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" aria-label="ok" />
            ) : c.required ? (
              <XCircle className="mt-0.5 h-4 w-4 text-red-600" aria-label="falhou" />
            ) : (
              <MinusCircle className="mt-0.5 h-4 w-4 text-amber-600" aria-label="opcional indisponível" />
            )}
            <span>
              {c.label}
              {!c.ok && <span className="text-slate-500"> — {c.message ?? c.code}</span>}
            </span>
          </li>
        ))}
      </ul>
      {result.rateLimit.perHourRemaining !== null && (
        <p className="text-xs text-slate-500">
          Pedidos restantes: {result.rateLimit.perMinuteRemaining ?? "—"}/min, {result.rateLimit.perHourRemaining}/hora
        </p>
      )}
    </div>
  );
}
