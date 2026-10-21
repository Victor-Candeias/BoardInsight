import { Alert } from "@/components/ui/alert";
import { formatDateTime } from "@/lib/format";

/** Data de referência dos dados e aviso quando a última sincronização é antiga. */
export function DataAsOf({ dataAsOf, stale }: { dataAsOf: string | null; stale: boolean }) {
  if (!dataAsOf)
    return <Alert variant="warning">Ainda não existem dados sincronizados para este board.</Alert>;
  if (stale)
    return (
      <Alert variant="warning">
        Os dados podem estar desatualizados: última sincronização com sucesso em {formatDateTime(dataAsOf)}.
      </Alert>
    );
  return <p className="text-sm text-slate-500">Dados de {formatDateTime(dataAsOf)}</p>;
}
