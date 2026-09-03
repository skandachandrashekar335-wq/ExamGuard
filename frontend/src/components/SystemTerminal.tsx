"use client";

import { useEffect, useRef } from "react";

interface SystemTerminalProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  subProgress: number;
}

interface LogLine {
  text: string;
  type: "system" | "success" | "warning" | "info" | "data" | "error";
  stage: string;
}

const STAGE_LINES: Record<string, LogLine[]> = {
  ready: [
    { text: "examguard v0.7.0 — identity verification", type: "system", stage: "ready" },
    { text: "waiting for scroll input...", type: "info", stage: "ready" },
  ],
  detect: [
    { text: "[detect] liveness check initiated", type: "system", stage: "detect" },
    { text: "analyzing facial depth map", type: "info", stage: "detect" },
    { text: "blink detection: active", type: "info", stage: "detect" },
    { text: "texture analysis: processing", type: "info", stage: "detect" },
    { text: "3d structure validation: active", type: "info", stage: "detect" },
  ],
  verify: [
    { text: "[verify] 1:N identity matching started", type: "system", stage: "verify" },
    { text: "loading enrollment templates", type: "info", stage: "verify" },
    { text: "computing similarity scores", type: "info", stage: "verify" },
    { text: "top match confidence: 0.94", type: "data", stage: "verify" },
    { text: "threshold: 0.85", type: "data", stage: "verify" },
  ],
  decide: [
    { text: "[decide] evaluating evidence", type: "system", stage: "decide" },
    { text: "liveness: PASS", type: "success", stage: "decide" },
    { text: "identity match: PASS", type: "success", stage: "decide" },
    { text: "confidence: 0.94 > 0.85", type: "data", stage: "decide" },
    { text: "decision: ALLOW", type: "success", stage: "decide" },
  ],
  authorize: [
    { text: "[authorize] entry verification complete", type: "system", stage: "authorize" },
    { text: "status: VERIFIED", type: "success", stage: "authorize" },
  ],
};

export default function SystemTerminal({ stage, subProgress }: SystemTerminalProps) {
  const linesRef = useRef<LogLine[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevStageRef = useRef<string>("");
  const lineIndexRef = useRef(0);

  useEffect(() => {
    if (stage !== prevStageRef.current) {
      prevStageRef.current = stage;
      lineIndexRef.current = 0;

      const newLines = STAGE_LINES[stage] || [];
      linesRef.current = [...linesRef.current, ...newLines];
    }
  }, [stage]);

  const visibleCount = Math.min(
    linesRef.current.length,
    Math.floor(subProgress * linesRef.current.length * 1.2) + 1
  );
  const visibleLines = linesRef.current.slice(0, visibleCount);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [visibleLines.length]);

  const typeColor: Record<string, string> = {
    system: "var(--accent-cyan)",
    success: "var(--accent-emerald)",
    warning: "var(--accent-amber)",
    error: "var(--accent-rose)",
    info: "var(--text-tertiary)",
    data: "var(--text-secondary)",
  };

  return (
    <div className="font-mono text-[0.55rem] sm:text-[0.6rem] leading-relaxed">
      {/* Terminal chrome */}
      <div className="flex items-center gap-1.5 mb-1.5 px-1">
        <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-cyan)] opacity-40" />
        <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-emerald)] opacity-40" />
        <div className="w-1.5 h-1.5 rounded-full bg-[var(--accent-amber)] opacity-40" />
        <span className="ml-2 text-[0.5rem] text-[var(--text-tertiary)] opacity-30 tracking-wider">examguard</span>
      </div>

      {/* Lines */}
      <div ref={containerRef} className="max-h-[160px] overflow-hidden pr-1 space-y-0.5">
        {visibleLines.map((line, i) => (
          <div
            key={`${line.stage}-${i}`}
            className="flex gap-2 opacity-0 animate-[eg-line-in_0.2s_ease-out_forwards]"
            style={{ animationDelay: `${Math.min(i * 40, 200)}ms` }}
          >
            <span className="text-[var(--text-tertiary)] opacity-20 select-none flex-shrink-0">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span style={{ color: typeColor[line.type] }}>{line.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
