import { NavLink, Outlet } from "react-router";
import { NAV_ITEMS } from "@/components/nav";
import { SyncButton } from "@/components/SyncButton";
import { useActiveBoard } from "@/hooks/useActiveBoard";
import { cn } from "@/lib/utils";

export function Layout() {
  const [boardId] = useActiveBoard();
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white">
        <div className="px-4 py-5 text-lg font-bold tracking-tight">BoardInsight</div>
        <nav className="flex flex-col gap-0.5 px-2" aria-label="Navegação principal">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 hover:bg-slate-100",
                  isActive && "bg-slate-100 font-medium text-slate-900",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-4 border-b border-slate-200 bg-white px-6">
          {boardId !== null && <SyncButton boardId={boardId} />}
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
