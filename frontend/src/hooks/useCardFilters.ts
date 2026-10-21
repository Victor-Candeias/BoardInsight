import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router";
import { CARD_FILTER_KEYS, type CardQuery } from "@/api/cards";
import type { PeriodQuery } from "@/api/dashboard";

/** Filtros guardados nos parâmetros do URL (partilháveis e mantidos ao recarregar). */
const NO_KEYS: string[] = [];

export function useCardFilters(extraKeys: string[] = NO_KEYS) {
  const [params, setParams] = useSearchParams();
  const keys = useMemo(() => [...CARD_FILTER_KEYS, ...extraKeys], [extraKeys]);

  const query = useMemo(() => {
    const q: CardQuery & PeriodQuery = {};
    for (const key of keys) {
      const value = params.get(key);
      if (value) q[key as keyof (CardQuery & PeriodQuery)] = value;
    }
    return q;
  }, [params, keys]);

  const setFilters = useCallback(
    (updates: Record<string, string | null | undefined>) => {
      setParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(updates)) {
            if (value) next.set(key, value);
            else next.delete(key);
          }
          if (!("page" in updates)) next.delete("page");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );
  const setFilter = useCallback((key: string, value: string | null | undefined) => setFilters({ [key]: value }), [setFilters]);

  const clear = useCallback(() => setParams(new URLSearchParams(), { replace: true }), [setParams]);
  const active = CARD_FILTER_KEYS.filter((k) => params.get(k)).length;

  return { query, setFilter, setFilters, clear, active };
}
