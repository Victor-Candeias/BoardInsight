import { Navigate, Route, Routes } from "react-router";
import { Layout } from "@/components/Layout";
import { BoardDetailPage } from "@/pages/BoardDetailPage";
import { CardDetailPage } from "@/pages/CardDetailPage";
import { CardsPage } from "@/pages/CardsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { BoardsPage } from "@/pages/BoardsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="boards" element={<BoardsPage />} />
        <Route path="boards/:boardId" element={<BoardDetailPage />} />
        <Route path="cards" element={<CardsPage />} />
        <Route path="cards/:cardId" element={<CardDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
