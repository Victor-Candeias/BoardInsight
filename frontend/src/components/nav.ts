import { BarChart3, CalendarClock, TrendingUp, LayoutGrid, ListTodo, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Dashboard", icon: BarChart3 },
  { to: "/cards", label: "Cartões", icon: ListTodo },
  { to: "/throughput", label: "Throughput", icon: TrendingUp },
  { to: "/deadlines", label: "Prazos", icon: CalendarClock },
  { to: "/boards", label: "Boards", icon: LayoutGrid },
];
