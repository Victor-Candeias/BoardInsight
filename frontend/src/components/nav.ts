import { Home, LayoutGrid, ListTodo, type LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Início", icon: Home },
  { to: "/cards", label: "Cartões", icon: ListTodo },
  { to: "/boards", label: "Boards", icon: LayoutGrid },
];
