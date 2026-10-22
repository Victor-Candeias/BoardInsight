import { Activity, AreaChart, BarChart3, FileText, Flag, OctagonAlert, CalendarClock, TrendingUp, LayoutGrid, Users, ListTodo, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: BarChart3 },
  { to: "/cards", label: "Cartões", icon: ListTodo },
  { to: "/throughput", label: "Throughput", icon: TrendingUp },
  { to: "/flow", label: "Fluxo", icon: Activity },
  { to: "/cfd", label: "CFD", icon: AreaChart },
  { to: "/blockers", label: "Bloqueios", icon: OctagonAlert },
  { to: "/sprints", label: "Sprints", icon: Flag },
  { to: "/deadlines", label: "Prazos", icon: CalendarClock },
  { to: "/developers", label: "Developers", icon: Users },
  { to: "/reports", label: "Relatórios", icon: FileText },
  { to: "/boards", label: "Boards", icon: LayoutGrid },
];
