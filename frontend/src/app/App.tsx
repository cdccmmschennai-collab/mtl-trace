import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";
import { TraceabilityPage } from "../pages/Traceability/TraceabilityPage";
import { WorkspaceRoute } from "../pages/Workspace/WorkspacePage";

export function App() {
  return (
    <BrowserRouter>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <Routes>
        <Route path="/" element={<WorkspaceRoute />} />
        <Route path="/scopes/:milestoneId" element={<WorkspaceRoute />} />
        <Route path="/traceability" element={<TraceabilityPage />} />
        {/* Earlier URLs (milestone list, create page, workspace tabs) lead into the workspace. */}
        <Route path="/milestones/new" element={<Navigate to="/" replace />} />
        <Route path="/milestones/:id/*" element={<LegacyMilestoneRedirect />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

function LegacyMilestoneRedirect() {
  const { id } = useParams();
  return <Navigate to={`/scopes/${id}`} replace />;
}
