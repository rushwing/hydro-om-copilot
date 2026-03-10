import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { DiagnosisPage } from "@/pages/DiagnosisPage";
import { HistoryPage } from "@/pages/HistoryPage";

function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-surface-border bg-surface-card px-6">
      <div className="mx-auto flex max-w-screen-xl items-center gap-6 py-3">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-4">
          <span className="text-amber text-xl">⚡</span>
          <span className="font-display text-lg font-semibold tracking-wide text-text-primary">
            水电运维
          </span>
          <span className="text-xs font-medium text-amber px-1.5 py-0.5 border border-amber/30 rounded bg-amber/10 ml-1">
            AI 诊断辅助
          </span>
        </div>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                isActive
                  ? "text-amber border-b-2 border-amber"
                  : "text-text-secondary hover:text-text-primary"
              }`
            }
          >
            故障诊断
          </NavLink>
          <NavLink
            to="/history"
            className={({ isActive }) =>
              `px-4 py-1.5 text-sm font-medium rounded transition-colors ${
                isActive
                  ? "text-amber border-b-2 border-amber"
                  : "text-text-secondary hover:text-text-primary"
              }`
            }
          >
            历史记录
          </NavLink>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Status indicator */}
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          系统就绪
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-surface font-sans text-text-primary">
        <Nav />
        <Routes>
          <Route path="/" element={<DiagnosisPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
