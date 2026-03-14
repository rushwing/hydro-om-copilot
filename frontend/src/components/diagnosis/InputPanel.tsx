import { useState, useRef, type FormEvent, type DragEvent } from "react";
import type { DiagnosisRequest } from "@/types/diagnosis";

interface InputPanelProps {
  onSubmit: (request: DiagnosisRequest) => void;
  onAbort: () => void;
  isRunning: boolean;
}

const UNITS = ["#1机", "#2机", "#3机", "#4机"];
const DEVICES = ["上导轴承", "下导轴承", "推力轴承", "调速器", "冷却水系统", "主变"];
const ANOMALIES = ["振动", "摆度", "温度高", "油压低", "流量异常", "泄漏", "启动失败"];

export function InputPanel({ onSubmit, onAbort, isRunning }: InputPanelProps) {
  const [query, setQuery] = useState("");
  const [selectedUnit, setSelectedUnit] = useState<string | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null);
  const [selectedAnomalies, setSelectedAnomalies] = useState<string[]>([]);
  const [imageBase64, setImageBase64] = useState<string | undefined>();
  const [imageName, setImageName] = useState<string | undefined>();
  const [imagePreview, setImagePreview] = useState<string | undefined>();
  const [isDragging, setIsDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const toggleUnit = (u: string) => setSelectedUnit((prev) => (prev === u ? null : u));
  const toggleDevice = (d: string) => setSelectedDevice((prev) => (prev === d ? null : d));
  const toggleAnomaly = (a: string) =>
    setSelectedAnomalies((prev) =>
      prev.includes(a) ? prev.filter((x) => x !== a) : [...prev, a],
    );

  const buildSuggestion = () => {
    const parts: string[] = [];
    if (selectedUnit) parts.push(selectedUnit);
    if (selectedDevice) parts.push(selectedDevice);
    if (selectedAnomalies.length > 0) parts.push(`出现${selectedAnomalies.join("、")}异常`);
    return parts.join("");
  };

  const fillSuggestion = () => {
    const suggestion = buildSuggestion();
    if (suggestion) setQuery(suggestion);
  };

  const processImageFile = (file: File) => {
    setImageName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      setImagePreview(dataUrl);
      setImageBase64(dataUrl.split(",")[1]);
    };
    reader.readAsDataURL(file);
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processImageFile(file);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (isRunning) return;
    const file = e.dataTransfer.files?.[0];
    if (file && file.type.startsWith("image/")) processImageFile(file);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (isRunning) return;
    setIsDragging(true);
  };

  const removeImage = () => {
    setImageBase64(undefined);
    setImageName(undefined);
    setImagePreview(undefined);
    if (fileRef.current) fileRef.current.value = "";
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSubmit({
      query: query.trim(),
      unit_id: selectedUnit ?? undefined,
      image_base64: imageBase64,
    });
  };

  const chipBase =
    "px-2.5 py-1 rounded text-xs font-medium border transition-all cursor-pointer select-none disabled:opacity-40 disabled:cursor-not-allowed";
  const chipInactive = `${chipBase} border-surface-border bg-surface-elevated text-text-secondary hover:border-amber/50 hover:text-text-primary`;
  const chipActive = `${chipBase} border-amber bg-amber/10 text-amber`;

  const hasSuggestion = !query && (selectedUnit || selectedDevice || selectedAnomalies.length > 0);

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {/* Unit selector */}
      <div>
        <label className="block text-xs text-text-muted mb-2 font-display uppercase tracking-wider">
          机组编号（可选）
        </label>
        <div className="flex flex-wrap gap-2">
          {UNITS.map((u) => (
            <button
              key={u}
              type="button"
              onClick={() => toggleUnit(u)}
              className={selectedUnit === u ? chipActive : chipInactive}
              disabled={isRunning}
            >
              {u}
            </button>
          ))}
        </div>
      </div>

      {/* Device selector */}
      <div>
        <label className="block text-xs text-text-muted mb-2 font-display uppercase tracking-wider">
          设备部件（可选）
        </label>
        <div className="flex flex-wrap gap-2">
          {DEVICES.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => toggleDevice(d)}
              className={selectedDevice === d ? chipActive : chipInactive}
              disabled={isRunning}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {/* Anomaly chips */}
      <div>
        <label className="block text-xs text-text-muted mb-2 font-display uppercase tracking-wider">
          异常类型（可多选）
        </label>
        <div className="flex flex-wrap gap-2">
          {ANOMALIES.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => toggleAnomaly(a)}
              className={selectedAnomalies.includes(a) ? chipActive : chipInactive}
              disabled={isRunning}
            >
              {a}
            </button>
          ))}
        </div>
      </div>

      {/* Auto-suggestion fill */}
      {hasSuggestion && (
        <div className="flex items-center gap-2 rounded border border-amber/20 bg-amber/5 px-3 py-2">
          <span className="text-xs text-text-secondary flex-1 truncate">
            建议描述：<span className="text-amber">{buildSuggestion()}</span>
          </span>
          <button
            type="button"
            onClick={fillSuggestion}
            className="text-xs font-medium text-amber border border-amber/40 px-2 py-0.5 rounded hover:bg-amber/10 transition-colors shrink-0"
          >
            填入描述
          </button>
        </div>
      )}

      {/* Textarea */}
      <div>
        <label className="block text-xs text-text-muted mb-2 font-display uppercase tracking-wider">
          异常描述
        </label>
        <textarea
          rows={4}
          placeholder="描述异常现象，例如：#1机在满负荷运行时，导叶开度反馈与给定偏差约 8%，油压装置压力持续偏低，已持续约 30 分钟…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full resize-none rounded border border-surface-border bg-surface-elevated px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:ring-2 focus:ring-amber/50 focus:border-amber/50 transition-colors"
          disabled={isRunning}
        />
      </div>

      {/* Image upload */}
      <div>
        <label className="block text-xs text-text-muted mb-2 font-display uppercase tracking-wider">
          上传截图（可选）
        </label>
        {imagePreview ? (
          <div className="relative inline-block">
            <img
              src={imagePreview}
              alt="preview"
              className="h-20 w-auto rounded border border-surface-border object-cover"
            />
            <button
              type="button"
              onClick={removeImage}
              disabled={isRunning}
              className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white text-xs leading-none hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ×
            </button>
            {imageName && (
              <p className="mt-1 text-xs text-text-muted truncate max-w-[160px]">{imageName}</p>
            )}
          </div>
        ) : (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={() => setIsDragging(false)}
            onClick={() => !isRunning && fileRef.current?.click()}
            className={`flex flex-col items-center justify-center rounded border-2 border-dashed py-4 text-xs transition-colors ${
              isRunning
                ? "cursor-not-allowed border-surface-border bg-surface-elevated text-text-muted opacity-40"
                : isDragging
                ? "cursor-pointer border-amber bg-amber/5 text-amber"
                : "cursor-pointer border-surface-border bg-surface-elevated text-text-muted hover:border-amber/40 hover:text-text-secondary"
            }`}
          >
            <span className="text-lg mb-1">📎</span>
            <span>拖拽或点击上传截图</span>
          </div>
        )}
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleImageChange}
        />
      </div>

      {/* Submit / abort */}
      {isRunning ? (
        <button
          type="button"
          onClick={onAbort}
          className="w-full rounded bg-red-900/50 border border-red-700 px-4 py-2.5 text-sm font-semibold text-red-400 hover:bg-red-900 transition-colors"
        >
          停止诊断
        </button>
      ) : (
        <button
          type="submit"
          disabled={!query.trim()}
          className="w-full rounded bg-amber px-4 py-2.5 text-sm font-bold font-display tracking-wider text-surface uppercase hover:bg-amber-glow disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          style={{ boxShadow: query.trim() ? "0 0 12px rgba(245,158,11,0.4)" : "none" }}
        >
          开始诊断
        </button>
      )}
    </form>
  );
}
