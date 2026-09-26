import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { CreateMilestonePage } from "../pages/CreateMilestone/CreateMilestonePage";
import { HomePage } from "../pages/Home/HomePage";
import { WorkspacePage } from "../pages/MilestoneWorkspace/WorkspacePage";
import { AppShell } from "./AppShell";

export function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/milestones/new" element={<CreateMilestonePage />} />
          <Route path="/milestones/:id" element={<Navigate to="scope" replace />} />
          <Route path="/milestones/:id/:tab" element={<WorkspacePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
