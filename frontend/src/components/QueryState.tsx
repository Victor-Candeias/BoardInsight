import { Alert } from "@/components/ui/alert";

export function ErrorAlert({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Erro inesperado";
  return (
    <Alert variant="error">
      {message}
    </Alert>
  );
}

export function Loading({ label = "A carregar…" }: { label?: string }) {
  return <p className="text-sm text-slate-500">{label}</p>;
}
