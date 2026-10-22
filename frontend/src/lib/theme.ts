import { useCallback, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

/** Mesma chave lida pelo script em `index.html` que aplica o tema antes do arranque do React. */
export const THEME_KEY = "boardinsight.theme";
const listeners = new Set<() => void>();

export function readTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("dark", theme === "dark");
}

export function setTheme(theme: Theme) {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Sem armazenamento (ex.: modo privado): o tema vale só para esta sessão.
  }
  applyTheme(theme);
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  const onStorage = (e: StorageEvent) => {
    if (e.key !== THEME_KEY) return;
    applyTheme(readTheme());
    listener();
  };
  listeners.add(listener);
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Tema claro/escuro, persistido em localStorage para a próxima abertura da app. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "light" as Theme);
  return [theme, useCallback(setTheme, [])];
}
