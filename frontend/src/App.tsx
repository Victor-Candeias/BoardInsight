import { Navigate, Route, Routes } from "react-router";
import { Layout } from "@/components/Layout";
import { BlockersPage } from "@/pages/BlockersPage";
import { BoardDetailPage } from "@/pages/BoardDetailPage";
import { CardDetailPage } from "@/pages/CardDetailPage";
import { CardsPage } from "@/pages/CardsPage";
import { CfdPage } from "@/pages/CfdPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { DeadlinesPage } from "@/pages/DeadlinesPage";
import { DevelopersPage } from "@/pages/DevelopersPage";
import { FlowPage } from "@/pages/FlowPage";
import { ThroughputPage } from "@/pages/ThroughputPage";
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
        <Route path="throughput" element={<ThroughputPage />} />
        <Route path="flow" element={<FlowPage />} />
        <Route path="cfd" element={<CfdPage />} />
        <Route path="blockers" element={<BlockersPage />} />
        <Route path="deadlines" element={<DeadlinesPage />} />
        <Route path="developers" element={<DevelopersPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
