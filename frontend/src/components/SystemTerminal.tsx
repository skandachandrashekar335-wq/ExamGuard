"use client";

import { useState, useEffect } from "react";

interface SystemTerminalProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
}

const STAGE_LOGS: Record<string, string[]> = {
  ready: [
    "System initialized",
    "Awaiting verification input",
  ],
  detect: [
    "Detection stage initialized",
    "Scanner frame active",
    "Awaiting face input",
  ],
  verify: [
    "Verification stage ready",
    "Identity + context linkage prepared",
    "Awaiting verification provider",
  ],
  decide: [
    "Evidence collection ready",
    "Decision engine standing by",
    "Awaiting evidence signals",
  ],
  authorize: [
    "Authorization stage reached",
    "Awaiting authoritative decision",
    "No entry authorized without decision",
  ],
};

export default function SystemTerminal({ stage }: SystemTerminalProps) {
  const [lines, setLines] = useState<string[]>([]);
  const [currentLine, setCurrentLine] = useState("");

  useEffect(() => {
    const logs = STAGE_LOGS[stage] || [];
    setLines([]);
    setCurrentLine("");

    let lineIdx = 0;
    let charIdx = 0;

    const typeInterval = setInterval(() => {
      if (lineIdx >= logs.length) {
        clearInterval(typeInterval);
        return;
      }

      const line = logs[lineIdx];
      if (charIdx <= line.length) {
        setCurrentLine(line.slice(0, charIdx));
        charIdx++;
      } else {
        setLines((prev) => [...prev, line]);
        setCurrentLine("");
        lineIdx++;
        charIdx = 0;
      }
    }, 30);

    return () => clearInterval(typeInterval);
  }, [stage]);

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg overflow-hidden font-mono text-xs">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--border)]">
        <div className="w-2 h-2 rounded-full bg-[var(--accent-cyan)] opacity-60" />
        <div className="w-2 h-2 rounded-full bg-[var(--accent-amber)] opacity-60" />
        <div className="w-2 h-2 rounded-full bg-[var(--text-tertiary)] opacity-60" />
        <span className="eg-label ml-2">SYSTEM TERMINAL</span>
      </div>
      <div className="p-4 min-h-[120px] max-h-[180px] overflow-y-auto">
        {lines.map((line, i) => (
          <div key={i} className="text-[var(--text-tertiary)]">
            <span className="text-[var(--accent-cyan)] opacity-60">&gt;</span>{" "}
            {line}
          </div>
        ))}
        {currentLine && (
          <div className="text-[var(--text-secondary)]">
            <span className="text-[var(--accent-cyan)] opacity-60">&gt;</span>{" "}
            {currentLine}
            <span className="eg-cursor inline-block w-[6px] h-[12px] bg-[var(--accent-cyan)] ml-[2px] align-middle" />
          </div>
        )}
        {!currentLine && lines.length > 0 && (
          <div className="text-[var(--text-tertiary)] mt-1">
            <span className="text-[var(--accent-cyan)] opacity-60">&gt;</span>{" "}
            <span className="eg-cursor inline-block w-[6px] h-[12px] bg-[var(--accent-cyan)] ml-[2px] align-middle" />
          </div>
        )}
      </div>
    </div>
  );
}
