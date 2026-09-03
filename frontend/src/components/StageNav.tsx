"use client";

import React from "react";

interface StageNavProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  onStageClick: (stageIndex: number) => void;
}

const STAGES = [
  { id: "detect", num: "01", label: "DETECT" },
  { id: "verify", num: "02", label: "VERIFY" },
  { id: "decide", num: "03", label: "DECIDE" },
  { id: "authorize", num: "04", label: "AUTHORIZE" },
];

const STAGE_ORDER = ["ready", "detect", "verify", "decide", "authorize"];

function StageNavInner({ stage, onStageClick }: StageNavProps) {
  const currentIdx = STAGE_ORDER.indexOf(stage);

  return (
    <nav className="flex items-center gap-0" role="navigation" aria-label="Verification stages">
      {STAGES.map((s, i) => {
        const sIdx = STAGE_ORDER.indexOf(s.id);
        const isActive = s.id === stage;
        const isPast = currentIdx > sIdx;

        return (
          <div key={s.id} className="flex items-center">
            <button
              onClick={() => onStageClick(sIdx)}
              className={`eg-focusable flex items-center gap-1.5 px-2.5 py-1.5 text-[0.55rem] font-[var(--font-mono)] tracking-[0.1em] uppercase transition-all duration-200 ${
                isActive
                  ? "text-[var(--white)]"
                  : isPast
                  ? "text-[var(--gray-400)] hover:text-[var(--white)]"
                  : "text-[var(--gray-600)] hover:text-[var(--gray-400)]"
              }`}
              aria-current={isActive ? "step" : undefined}
            >
              <span
                className={`w-1 h-1 rounded-full transition-colors duration-200 ${
                  isActive ? "bg-[var(--white)]" : isPast ? "bg-[var(--gray-400)]" : "bg-[var(--gray-700)]"
                }`}
              />
              <span>{s.num}</span>
              <span className="hidden sm:inline">{s.label}</span>
            </button>

            {/* Connector */}
            {i < STAGES.length - 1 && (
              <div className="w-6 sm:w-10 h-px mx-1 eg-progress-line" style={{ "--progress": isPast ? "100%" : isActive ? "50%" : "0%" } as React.CSSProperties} />
            )}
          </div>
        );
      })}
    </nav>
  );
}

const StageNav = React.memo(StageNavInner);
export default StageNav;
