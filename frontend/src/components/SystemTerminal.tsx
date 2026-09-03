"use client";

import React, { useEffect, useRef } from "react";

interface SystemTerminalProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
}

interface LogLine {
  text: string;
  type: "system" | "status" | "awaiting";
  stage: string;
}

const STAGE_LINES: Record<string, LogLine[]> = {
  ready: [
    { text: "[system] ready", type: "system", stage: "ready" },
    { text: "[system] awaiting verification input", type: "awaiting", stage: "ready" },
  ],
  detect: [
    { text: "[detect] detection stage active", type: "system", stage: "detect" },
    { text: "[detect] awaiting liveness input", type: "awaiting", stage: "detect" },
  ],
  verify: [
    { text: "[verify] identity matching stage", type: "system", stage: "verify" },
    { text: "[verify] student — not connected", type: "awaiting", stage: "verify" },
    { text: "[verify] hall ticket — not loaded", type: "awaiting", stage: "verify" },
  ],
  decide: [
    { text: "[decide] evidence evaluation stage", type: "system", stage: "decide" },
    { text: "[decide] awaiting evidence", type: "awaiting", stage: "decide" },
    { text: "[decide] evidence ≠ decision", type: "status", stage: "decide" },
  ],
  authorize: [
    { text: "[authorize] entry verification stage", type: "system", stage: "authorize" },
    { text: "[authorize] awaiting verified decision", type: "awaiting", stage: "authorize" },
  ],
};

function SystemTerminalInner({ stage }: SystemTerminalProps) {
  const linesRef = useRef<LogLine[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevStageRef = useRef<string>("");

  useEffect(() => {
    if (stage !== prevStageRef.current) {
      prevStageRef.current = stage;
      const newLines = STAGE_LINES[stage] || [];
      linesRef.current = [...linesRef.current, ...newLines];
      if (containerRef.current) {
        containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }
    }
  }, [stage]);

  const lines = linesRef.current;

  return (
    <div className="font-[var(--font-mono)] text-[0.5rem] sm:text-[0.55rem] leading-relaxed tracking-wide">
      <div ref={containerRef} className="max-h-[120px] overflow-hidden space-y-0.5">
        {lines.map((line, i) => (
          <div
            key={`${line.stage}-${i}`}
            className="flex gap-2"
            style={{ animation: `eg-line-in 0.15s ease-out ${Math.min(i * 30, 150)}ms both` }}
          >
            <span className="text-[var(--gray-700)] select-none flex-shrink-0 w-4 text-right">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className={
              line.type === "system" ? "text-[var(--gray-400)]"
              : line.type === "status" ? "text-[var(--gray-300)]"
              : "text-[var(--gray-500)]"
            }>
              {line.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

const SystemTerminal = React.memo(SystemTerminalInner);
export default SystemTerminal;
