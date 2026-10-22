import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogIn, LogOut } from "lucide-react";
import { AUTH_ME_KEY, fetchMe, login, logout, SIGNED_OUT, type AuthState } from "@/api/auth";
import { UNAUTHORIZED_EVENT } from "@/api/client";
import { ErrorAlert, Loading } from "@/components/QueryState";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/input";

export function useAuth() {
  return useQuery({ queryKey: AUTH_ME_KEY, queryFn: fetchMe, staleTime: Infinity, retry: false });
}

/** Mostra o login enquanto não houver sessão (só com AUTH_ENABLED=true no backend). */
export function AuthGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { data, error, isPending, refetch } = useAuth();

  useEffect(() => {
    const signOut = () => queryClient.setQueryData<AuthState>(AUTH_ME_KEY, SIGNED_OUT);
    window.addEventListener(UNAUTHORIZED_EVENT, signOut);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, signOut);
  }, [queryClient]);

  if (isPending) return <CenteredLoading />;
  if (error)
    return (
      <div className="mx-auto mt-24 max-w-md space-y-3 p-6">
        <ErrorAlert error={error} />
        <Button variant="outline" onClick={() => refetch()}>
          Tentar novamente
        </Button>
      </div>
    );
  if (data.authEnabled && !data.user) return <LoginPage />;
  return <>{children}</>;
}

function CenteredLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Loading />
    </div>
  );
}

export function LoginPage() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => login(email.trim(), password),
    onSuccess: (state) => {
      queryClient.setQueryData(AUTH_ME_KEY, state);
      // Pedidos que falharam com 401 antes do login voltam a ser feitos.
      void queryClient.invalidateQueries({ predicate: (q) => q.queryKey[0] !== AUTH_ME_KEY[0] });
    },
    onSettled: () => setPassword(""),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    mutation.mutate();
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <Card className="w-full max-w-sm">
        <CardHeader className="items-center gap-3 p-6 pb-2 text-center">
          <img src="/brand/logo.png" alt="BoardInsight" className="w-40 dark:rounded-lg dark:bg-white dark:p-1.5" width={480} height={337} />
          <CardTitle className="text-base">Iniciar sessão</CardTitle>
          <CardDescription>Use o email e a password da sua conta da empresa.</CardDescription>
        </CardHeader>
        <CardContent className="p-6 pt-2">
          <form className="space-y-4" onSubmit={submit}>
            <Label>
              Email
              <Input
                type="email"
                name="email"
                autoComplete="username"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </Label>
            <Label>
              Password
              <Input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </Label>
            {mutation.error && (
              <Alert variant="error">{mutation.error instanceof Error ? mutation.error.message : "Erro inesperado"}</Alert>
            )}
            <Button type="submit" className="w-full" disabled={mutation.isPending}>
              <LogIn className="h-4 w-4" aria-hidden />
              {mutation.isPending ? "A validar…" : "Entrar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export function UserMenu() {
  const queryClient = useQueryClient();
  const { data } = useAuth();
  const mutation = useMutation({
    mutationFn: logout,
    onSettled: () => {
      queryClient.setQueryData<AuthState>(AUTH_ME_KEY, SIGNED_OUT);
      // Os dados em cache não ficam disponíveis para a próxima sessão.
      queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== AUTH_ME_KEY[0] });
    },
  });
  const user = data?.user;
  if (!data?.authEnabled || !user) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="max-w-48 truncate text-sm text-slate-600" title={user.email}>
        {user.name}
      </span>
      <Button size="sm" variant="outline" onClick={() => mutation.mutate()} disabled={mutation.isPending} title="Terminar sessão">
        <LogOut className="h-4 w-4" aria-hidden />
        Terminar sessão
      </Button>
    </div>
  );
}
