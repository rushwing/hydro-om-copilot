import { useEffect } from "react";
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import { DiagnosisPage } from "@/pages/DiagnosisPage";
import { HistoryPage } from "@/pages/HistoryPage";
import { ManualPage } from "@/pages/ManualPage";
import { useAutoStore } from "@/store/autoStore";
import { useAutoDiagnosis } from "@/hooks/useAutoDiagnosis";
import logoUrl from "@/assets/logo.svg";

function Nav() {
  const { enabled, setEnabled, status } = useAutoStore();
  const { start, stop } = useAutoDiagnosis();

  const handleToggleAuto = async () => {
    if (enabled) {
      await stop();
      setEnabled(false);
    } else {
      await start();
    }
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-4 py-1.5 text-sm font-medium rounded transition-colors ${
      isActive
        ? "text-amber border-b-2 border-amber"
        : "text-text-secondary hover:text-text-primary"
    }`;

  return (
    <nav className="sticky top-0 z-50 border-b border-surface-border bg-surface-card px-6">
      <div className="mx-auto flex max-w-screen-xl items-center gap-6 py-3">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-4">
          <img src={logoUrl} alt="logo" className="h-8 w-8 object-contain" />
          <span className="font-display text-lg font-semibold tracking-wide text-text-primary">
            水电机组智能运维系统
          </span>
          <span className="text-xs font-medium text-amber px-1.5 py-0.5 border border-amber/30 rounded bg-amber/10 ml-1">
            AI 诊断辅助
          </span>
        </div>

        {/* Nav links */}
        <div className="flex items-center gap-1">
          <NavLink to="/" end className={navLinkClass}>
            故障诊断
          </NavLink>
          <NavLink to="/history" className={navLinkClass}>
            历史记录
          </NavLink>
          <NavLink to="/manual" className={navLinkClass}>
            操作手册
          </NavLink>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auto-diagnosis toggle + status */}
        <div className="flex items-center gap-3">
          {enabled && (
            <span className="px-2 py-0.5 text-xs rounded border border-amber/30 bg-amber/10 text-amber">
              🤖 自动诊断 {status?.running ? "运行中" : "已暂停"}
            </span>
          )}
          <button
            onClick={handleToggleAuto}
            className={`px-3 py-1 text-xs font-medium rounded border transition-colors ${
              enabled
                ? "border-surface-border text-text-secondary hover:text-text-primary hover:border-text-secondary"
                : "border-amber/30 bg-amber/10 text-amber hover:bg-amber/20"
            }`}
          >
            {enabled ? "关闭自动" : "自动诊断"}
          </button>

          {/* Status indicator */}
          <div className="flex items-center gap-2 text-xs text-text-secondary">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            系统就绪
          </div>
        </div>
      </div>
    </nav>
  );
}

function ToastStack() {
  const { toasts, dismissToast } = useAutoStore();

  useEffect(() => {
    if (toasts.length === 0) return;
    const latest = toasts[toasts.length - 1];
    const id = setTimeout(() => dismissToast(latest.id), 15000);
    return () => clearTimeout(id);
  }, [toasts, dismissToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map((t) => (
        <div
          key={t.id}
          className="flex items-start gap-3 rounded-lg border border-amber/30 bg-surface-card shadow-lg px-4 py-3 animate-result"
        >
          <span className="text-amber mt-0.5 shrink-0">⚠</span>
          <p className="text-xs text-text-secondary leading-relaxed flex-1">{t.message}</p>
          <button
            onClick={() => dismissToast(t.id)}
            className="text-text-muted hover:text-text-primary shrink-0 text-sm leading-none"
          >
            ✕
          </button>
        </div>
      ))}
    </div>
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
          <Route path="/manual" element={<ManualPage />} />
        </Routes>
        <ToastStack />
      </div>
    </BrowserRouter>
  );
}
