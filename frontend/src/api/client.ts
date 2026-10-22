export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | null | undefined | (string | number)[]>;

export function buildQuery(query?: Query): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.set(key, String(value));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export const UNAUTHORIZED_EVENT = "boardinsight:unauthorized";

export async function api<T>(path: string, init?: RequestInit & { query?: Query }): Promise<T> {
  const { query, ...rest } = init ?? {};
  const response = await fetch(`${path}${buildQuery(query)}`, {
    ...rest,
    headers: { Accept: "application/json", ...(rest.body ? { "Content-Type": "application/json" } : {}), ...rest.headers },
  });
  if (!response.ok) {
    // Sessão expirada/terminada: o AuthGate volta a mostrar o login.
    if (response.status === 401 && !path.startsWith("/api/v1/auth/")) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    let code = "http_error";
    let message = `Erro HTTP ${response.status}`;
    try {
      const body = await response.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message ?? body?.detail ?? message;
    } catch {
      /* resposta sem JSON */
    }
    throw new ApiError(response.status, code, typeof message === "string" ? message : JSON.stringify(message));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
