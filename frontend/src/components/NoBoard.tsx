import { Link } from "react-router";
import { Alert } from "@/components/ui/alert";

export function NoBoard() {
  return (
    <Alert variant="info">
      Nenhum board selecionado.{" "}
      <Link to="/boards" className="font-medium underline">
        Adicionar ou escolher um board
      </Link>
      .
    </Alert>
  );
}
