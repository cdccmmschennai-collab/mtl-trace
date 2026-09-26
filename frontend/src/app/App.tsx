import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { CreateMilestonePage } from "../pages/CreateMilestone/CreateMilestonePage";
import { HomePage } from "../pages/Home/HomePage";
import { WorkspacePage } from "../pages/MilestoneWorkspace/WorkspacePage";

export function App() {
  return (
    <BrowserRouter>
      <header className="topbar">
        <Link to="/" className="brand">
          CDC MTL Tool
        </Link>
        <span className="topbar-note">Local · engineering data consolidation &amp; comparison</span>
      </header>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/milestones/new" element={<CreateMilestonePage />} />
        <Route path="/milestones/:id" element={<Navigate to="scope" replace />} />
        <Route path="/milestones/:id/:tab" element={<WorkspacePage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
