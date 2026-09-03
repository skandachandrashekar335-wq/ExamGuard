"use client";

import { useState, useEffect, useRef } from "react";

interface SystemTerminalProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  subProgress: number;
}

interface TerminalLine {
  text: string;
  type: "system" | "info" | "status" | "warn";
}

const STAGE_ENTRIES: Record<string, TerminalLine[]> = {
  ready: [
    { text: "EXAMGUARD v1.0 — EXAMINATION SECURITY", type: "system" },
    { text: "System initialized", type: "status" },
    { text: "Awaiting interaction", type: "info" },
  ],
  detect: [
    { text: "DETECTION MODULE", type: "system" },
    { text: "Scanner frame active", type: "status" },
    { text: "Geometry visualization engaged", type: "info" },
  ],
  verify: [
    { text: "IDENTITY CONTEXT", type: "system" },
    { text: "Awaiting verification input", type: "info" },
    { text: "Hall ticket + identity linkage prepared", type: "status" },
  ],
  decide: [
    { text: "DECISION LAYER", type: "system" },
    { text: "Evidence signals collected", type: "status" },
    { text: "Awaiting evidence", type: "info" },
  ],
  authorize: [
    { text: "AUTHORIZATION", type: "system" },
    { text: "Awaiting authoritative decision", type: "info" },
    { text: "No entry authorized without decision", type: "warn" },
  ],
};

export default function SystemTerminal({ stage, subProgress }: SystemTerminalProps) {
  const [lines, setLines] = useState<TerminalLine[]>([]);
  const [currentLine, setCurrentLine] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const stageRef = useRef(stage);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (stage === stageRef.current) return;
    stageRef.current = stage;

    const entries = STAGE_ENTRIES[stage] || [];
    setLines([]);
    setCurrentLine("");
    setIsTyping(true);

    let lineIdx = 0;
    let charIdx = 0;

    const typeInterval = setInterval(() => {
      if (lineIdx >= entries.length) {
        clearInterval(typeInterval);
        setIsTyping(false);
        return;
      }

      const line = entries[lineIdx];
      if (charIdx <= line.text.length) {
        setCurrentLine(line.text.slice(0, charIdx));
        charIdx++;
      } else {
        setLines((prev) => [...prev, line]);
        setCurrentLine("");
        lineIdx++;
        charIdx = 0;
      }
    }, 25);

    return () => clearInterval(typeInterval);
  }, [stage]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines, currentLine]);

  const getTypeColor = (type: TerminalLine["type"]) => {
    switch (type) {
      case "system": return "text-[var(--accent-cyan)]";
      case "status": return "text-[var(--accent-emerald)]";
      case "info": return "text-[var(--text-secondary)]";
      case "warn": return "text-[var(--accent-amber)]";
    }
  };

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-lg overflow-hidden font-mono text-xs">
      <div className="flex items-center gap-2 px-4 py-2 border-b border-[var(--border)]">
        <div className="w-2 h-2 rounded-full bg-[var(--accent-cyan)] opacity-60" />
        <div className="w-2 h-2 rounded-full bg-[var(--accent-amber)] opacity-60" />
        <div className="w-2 h-2 rounded-full bg-[var(--text-tertiary)] opacity-60" />
        <span className="eg-label ml-2">SYSTEM TERMINAL</span>
        <span className="ml-auto eg-label text-[0.5rem] opacity-40">{stage.toUpperCase()}</span>
      </div>
      <div ref={scrollRef} className="p-4 min-h-[100px] max-h-[160px] overflow-y-auto">
        {lines.map((line, i) => (
          <div key={i} className={`${getTypeColor(line.type)}`}>
            <span className="text-[var(--text-tertiary)] opacity-40">&gt;</span>{" "}
            {line.text}
          </div>
        ))}
        {currentLine && (
          <div className="text-[var(--text-secondary)]">
            <span className="text-[var(--text-tertiary)] opacity-40">&gt;</span>{" "}
            {currentLine}
            <span className="eg-cursor inline-block w-[6px] h-[12px] bg-[var(--accent-cyan)] ml-[2px] align-middle opacity-70" />
          </div>
        )}
        {!isTyping && lines.length > 0 && (
          <div className="text-[var(--text-tertiary)] mt-1 opacity-30">
            <span>&gt;</span>{" "}
            <span className="eg-cursor inline-block w-[6px] h-[12px] bg-[var(--accent-cyan)] ml-[2px] align-middle" />
          </div>
        )}
      </div>
    </div>
  );
}
