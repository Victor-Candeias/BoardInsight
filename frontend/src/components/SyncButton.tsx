import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { enqueueSync, getJob, getSyncStatus, isActiveJob, syncStatusKey } from "@/api/sync";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export const JOB_POLL_MS = 2000;

export function SyncButton({ boardId }: { boardId: number }) {
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const status = useQuery({ queryKey: syncStatusKey(boardId), queryFn: () => getSyncStatus(boardId), refetchInterval: 60_000 });

  // Retoma o acompanhamento de um job já em curso (ex.: após recarregar a página).
  useEffect(() => {
    const latest = status.data?.latestJob;
    if (!jobId && isActiveJob(latest)) setJobId(latest!.id);
  }, [status.data, jobId]);

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (q) => (isActiveJob(q.state.data) || !q.state.data ? JOB_POLL_MS : false),
  });

  useEffect(() => {
    const data = job.data;
    if (!data || isActiveJob(data)) return;
    setJobId(null);
    if (data.status === "error") setError(data.error?.message ?? "A sincronização falhou");
    // Dados novos: invalidar tudo o que depende do board.
    void queryClient.invalidateQueries();
  }, [job.data, queryClient]);

  const mutation = useMutation({
    mutationFn: () => enqueueSync(boardId),
    onMutate: () => setError(null),
    onSuccess: ({ job }) => setJobId(job.id),
    onError: (e: Error) => setError(e.message),
  });

  const busy = mutation.isPending || jobId !== null;
  const s = status.data;

  return (
    <div className="flex items-center gap-3 text-sm">
      {s && (
        <span className={cn("flex items-center gap-1", s.stale ? "text-amber-700" : "text-slate-500")}>
          {s.stale && <AlertTriangle className="h-4 w-4" aria-hidden />}
          {s.lastSuccessfulSyncAt ? `Atualizado: ${formatDateTime(s.lastSuccessfulSyncAt)}` : "Nunca sincronizado"}
          {s.stale && s.lastSuccessfulSyncAt && " (dados desatualizados)"}
        </span>
      )}
      {error && (
        <span role="alert" className="text-red-700">
          {error}
        </span>
      )}
      <Button size="sm" variant="outline" onClick={() => mutation.mutate()} disabled={busy}>
        <RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} aria-hidden />
        {busy ? "A atualizar…" : "Atualizar"}
      </Button>
    </div>
  );
}
