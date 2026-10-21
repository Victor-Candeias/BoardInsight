import { Badge } from "@/components/ui/badge";
import type { Card } from "@/api/cards";

const STATUS_VARIANT: Record<string, "default" | "success" | "warning" | "danger" | "info"> = {
  backlog: "default",
  todo: "info",
  in_progress: "warning",
  done: "success",
  archived: "default",
  discarded: "default",
  unknown: "default",
};

const PRIORITY_VARIANT: Record<number, "default" | "warning" | "danger" | "info"> = { 1: "danger", 2: "warning", 3: "info", 4: "default" };

export function StatusBadge({ card }: { card: Pick<Card, "status" | "statusLabel"> }) {
  return <Badge variant={STATUS_VARIANT[card.status] ?? "default"}>{card.statusLabel}</Badge>;
}

export function PriorityBadge({ card }: { card: Pick<Card, "priority" | "priorityLabel"> }) {
  return <Badge variant={PRIORITY_VARIANT[card.priority] ?? "default"}>{card.priorityLabel}</Badge>;
}

export function CardFlags({ card }: { card: Pick<Card, "isBlocked" | "overdue" | "dueSoon" | "missing"> }) {
  return (
    <span className="inline-flex flex-wrap gap-1">
      {card.isBlocked && <Badge variant="danger">Bloqueado</Badge>}
      {card.overdue && <Badge variant="danger">Em atraso</Badge>}
      {card.dueSoon && <Badge variant="warning">Prazo próximo</Badge>}
      {card.missing && <Badge>Não encontrado na última sync</Badge>}
    </span>
  );
}
