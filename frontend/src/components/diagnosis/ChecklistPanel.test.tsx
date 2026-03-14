import { render, screen, fireEvent } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChecklistPanel } from "./ChecklistPanel";
import type { CheckStep } from "@/types/diagnosis";

const CHECKLIST_KEY = "hydro_om_checklist_states";

const steps: CheckStep[] = [
  { step: 1, action: "检查导叶开度反馈", expected: "开度一致" },
  { step: 2, action: "测量振动摆度实时值", expected: "摆度 <0.25mm", caution: "测量时机组不得升负荷" },
  { step: 3, action: "检查导叶接力器行程" },
];

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ChecklistPanel — rendering", () => {
  it("renders all step actions", () => {
    render(<ChecklistPanel steps={steps} />);
    expect(screen.getByText("检查导叶开度反馈")).toBeInTheDocument();
    expect(screen.getByText("测量振动摆度实时值")).toBeInTheDocument();
    expect(screen.getByText("检查导叶接力器行程")).toBeInTheDocument();
  });

  it("renders expected result text", () => {
    render(<ChecklistPanel steps={steps} />);
    expect(screen.getByText(/开度一致/)).toBeInTheDocument();
  });

  it("renders caution text", () => {
    render(<ChecklistPanel steps={steps} />);
    expect(screen.getByText(/测量时机组不得升负荷/)).toBeInTheDocument();
  });

  it("shows 0/3 progress initially", () => {
    render(<ChecklistPanel steps={steps} />);
    expect(screen.getByText(/3 步骤已完成/)).toBeInTheDocument();
    // Progress bar width = 0%
    const bar = document.querySelector('[style*="width: 0%"]');
    expect(bar).toBeInTheDocument();
  });
});

describe("ChecklistPanel — checkbox interaction", () => {
  it("toggles a step to checked on click", () => {
    render(<ChecklistPanel steps={steps} />);
    const checkboxes = screen.getAllByRole("button", { name: "标记完成" });
    fireEvent.click(checkboxes[0]);
    expect(screen.getByRole("button", { name: "取消勾选" })).toBeInTheDocument();
  });

  it("toggles a step back to unchecked on second click", () => {
    render(<ChecklistPanel steps={steps} />);
    const btn = screen.getAllByRole("button", { name: "标记完成" })[0];
    fireEvent.click(btn);
    const uncheckedBtn = screen.getByRole("button", { name: "取消勾选" });
    fireEvent.click(uncheckedBtn);
    expect(screen.getAllByRole("button", { name: "标记完成" })).toHaveLength(3);
  });
});

describe("ChecklistPanel — localStorage persistence", () => {
  it("writes checked state to localStorage with sessionId", () => {
    const setItem = vi.spyOn(window.localStorage, "setItem");
    render(<ChecklistPanel steps={steps} sessionId="session-123" />);
    const btn = screen.getAllByRole("button", { name: "标记完成" })[0];
    fireEvent.click(btn);
    expect(setItem).toHaveBeenCalledWith(
      CHECKLIST_KEY,
      expect.stringContaining("session-123"),
    );
  });

  it("loads persisted checked state on mount", () => {
    localStorage.setItem(CHECKLIST_KEY, JSON.stringify({ "session-abc": [1] }));
    render(<ChecklistPanel steps={steps} sessionId="session-abc" />);
    // Step 1 should be checked (aria-label = 取消勾选)
    expect(screen.getByRole("button", { name: "取消勾选" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "标记完成" })).toHaveLength(2);
  });

  it("does not persist when no sessionId", () => {
    const setItem = vi.spyOn(window.localStorage, "setItem");
    render(<ChecklistPanel steps={steps} />);
    const btn = screen.getAllByRole("button", { name: "标记完成" })[0];
    fireEvent.click(btn);
    expect(setItem).not.toHaveBeenCalled();
  });
});

describe("ChecklistPanel — callbacks", () => {
  it("calls onAllChecked(true) when all steps are checked", () => {
    const onAllChecked = vi.fn();
    render(<ChecklistPanel steps={steps} onAllChecked={onAllChecked} sessionId="s1" />);
    const btns = screen.getAllByRole("button", { name: "标记完成" });
    btns.forEach((b) => fireEvent.click(b));
    expect(onAllChecked).toHaveBeenLastCalledWith(true);
  });

  it("calls onAllChecked(false) when not all steps are checked", () => {
    const onAllChecked = vi.fn();
    render(<ChecklistPanel steps={steps} onAllChecked={onAllChecked} sessionId="s2" />);
    const btns = screen.getAllByRole("button", { name: "标记完成" });
    fireEvent.click(btns[0]);
    expect(onAllChecked).toHaveBeenCalledWith(false);
  });

  it("calls onCheckedChange with current Set on toggle", () => {
    const onCheckedChange = vi.fn();
    render(<ChecklistPanel steps={steps} onCheckedChange={onCheckedChange} />);
    const btn = screen.getAllByRole("button", { name: "标记完成" })[1];
    fireEvent.click(btn);
    const calls = onCheckedChange.mock.calls;
    const lastCall = calls[calls.length - 1]?.[0] as Set<number>;
    expect(lastCall).toBeInstanceOf(Set);
    expect(lastCall.has(2)).toBe(true);
  });
});

describe("ChecklistPanel — sessionId change", () => {
  it("resets checked state when sessionId changes", () => {
    localStorage.setItem(CHECKLIST_KEY, JSON.stringify({ "session-1": [1, 2] }));
    const { rerender } = render(<ChecklistPanel steps={steps} sessionId="session-1" />);
    expect(screen.getAllByRole("button", { name: "取消勾选" })).toHaveLength(2);

    // Switch to a session with no saved state
    rerender(<ChecklistPanel steps={steps} sessionId="session-new" />);
    expect(screen.getAllByRole("button", { name: "标记完成" })).toHaveLength(3);
  });
});
