import { useCallback, useSyncExternalStore } from "react";

const KEY = "boardinsight.activeBoardId";
const listeners = new Set<() => void>();

function read(): number | null {
  const value = Number(localStorage.getItem(KEY));
  return Number.isInteger(value) && value > 0 ? value : null;
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function setActiveBoardId(id: number | null) {
  if (id === null) localStorage.removeItem(KEY);
  else localStorage.setItem(KEY, String(id));
  listeners.forEach((l) => l());
}

/** Board ativo (persistido em localStorage e partilhado entre componentes). */
export function useActiveBoard(): [number | null, (id: number | null) => void] {
  const id = useSyncExternalStore(subscribe, read, () => null);
  return [id, useCallback(setActiveBoardId, [])];
}
