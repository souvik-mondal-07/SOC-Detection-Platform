import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/layout/AppLayout";
import AlertsPage from "./pages/AlertsPage";
import DashboardPage from "./pages/DashboardPage";
import DetectionRulesPage from "./pages/DetectionRulesPage";
import InvestigationDetailPage from "./pages/InvestigationDetailPage";
import InvestigationsPage from "./pages/InvestigationsPage";
import NotFoundPage from "./pages/NotFoundPage";
import SecurityEventsPage from "./pages/SecurityEventsPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="security-events" element={<SecurityEventsPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="detection-rules" element={<DetectionRulesPage />} />
        <Route path="investigations" element={<InvestigationsPage />} />
        <Route path="investigations/:investigationId" element={<InvestigationDetailPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
