import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useTheme();
  const dark = theme === "dark";
  const label = dark ? "Mudar para modo claro" : "Mudar para modo escuro";
  return (
    <Button size="sm" variant="outline" onClick={() => setTheme(dark ? "light" : "dark")} aria-label={label} title={label}>
      {dark ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
      {dark ? "Claro" : "Escuro"}
    </Button>
  );
}
