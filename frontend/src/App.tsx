import { Navigate, Route, Routes } from "react-router";
import { Layout } from "@/components/Layout";
import { HomePage } from "@/pages/HomePage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
