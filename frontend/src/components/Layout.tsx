import { Link, NavLink, Outlet } from "react-router";
import { NAV_GROUPS } from "@/components/nav";
import { BoardSelector } from "@/components/BoardSelector";
import { SyncButton } from "@/components/SyncButton";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { cn } from "@/lib/utils";

export function Layout() {
  const [boardId] = useActiveBoard();
  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
        <Link to="/" className="block px-5 pb-3 pt-4" aria-label="BoardInsight — página inicial">
          <img src="/brand/logo.png" alt="BoardInsight" className="mx-auto w-44" width={480} height={337} />
        </Link>
        <nav className="flex-1 space-y-4 overflow-y-auto px-3 pb-4" aria-label="Navegação principal">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <div className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.label}</div>
              <div className="flex flex-col gap-0.5">
                {group.items.map(({ to, label, icon: Icon }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === "/"}
                    className={({ isActive }) =>
                      cn(
                        "relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900",
                        isActive &&
                          "bg-brand-50 font-medium text-brand-800 before:absolute before:inset-y-1.5 before:left-0 before:w-1 before:rounded-full before:bg-linear-to-b before:from-brand-500 before:to-accent-500 hover:bg-brand-50",
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    {label}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-slate-100 px-5 py-3 text-[11px] text-slate-400">Dados Businessmap · só leitura</div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-14 items-center justify-between gap-4 border-b border-slate-200 bg-white/90 px-6 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="text-xs font-medium uppercase tracking-wide text-slate-400">Board</span>
            <BoardSelector />
          </div>
          {boardId !== null && <SyncButton boardId={boardId} />}
        </header>
        <main className="mx-auto w-full max-w-[1600px] flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
