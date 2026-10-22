import { Activity, AreaChart, BarChart3, BellRing, FileText, Flag, OctagonAlert, CalendarClock, TrendingUp, LayoutGrid, Users, ListTodo, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Visão geral",
    items: [
      { to: "/", label: "Atenção", icon: BellRing },
      { to: "/dashboard", label: "Dashboard", icon: BarChart3 },
    ],
  },
  {
    label: "Fluxo e entrega",
    items: [
      { to: "/throughput", label: "Throughput", icon: TrendingUp },
      { to: "/flow", label: "Fluxo", icon: Activity },
      { to: "/cfd", label: "CFD", icon: AreaChart },
      { to: "/blockers", label: "Bloqueios", icon: OctagonAlert },
      { to: "/deadlines", label: "Prazos", icon: CalendarClock },
      { to: "/sprints", label: "Sprints", icon: Flag },
    ],
  },
  {
    label: "Equipa",
    items: [{ to: "/developers", label: "Developers", icon: Users }],
  },
  {
    label: "Dados",
    items: [
      { to: "/cards", label: "Cartões", icon: ListTodo },
      { to: "/reports", label: "Relatórios", icon: FileText },
      { to: "/boards", label: "Boards", icon: LayoutGrid },
    ],
  },
];
