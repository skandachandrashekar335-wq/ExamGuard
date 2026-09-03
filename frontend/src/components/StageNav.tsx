"use client";

interface StageNavProps {
  stage: "ready" | "detect" | "verify" | "decide" | "authorize";
  onStageClick: (stage: string) => void;
}

const STAGES = [
  { id: "detect", num: "01", label: "DETECT" },
  { id: "verify", num: "02", label: "VERIFY" },
  { id: "decide", num: "03", label: "DECIDE" },
  { id: "authorize", num: "04", label: "AUTHORIZE" },
];

const STAGE_ORDER = ["ready", "detect", "verify", "decide", "authorize"];

export default function StageNav({ stage, onStageClick }: StageNavProps) {
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
              onClick={() => onStageClick(s.id)}
              className={`eg-focusable relative flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg text-[0.6rem] sm:text-[0.65rem] font-mono transition-all duration-300 ${
                isActive
                  ? "bg-[rgba(0,229,255,0.06)] text-[var(--accent-cyan)]"
                  : isPast
                  ? "text-[var(--accent-emerald)] hover:bg-white/[0.02]"
                  : "text-[var(--text-tertiary)] opacity-40 hover:opacity-60"
              }`}
              aria-current={isActive ? "step" : undefined}
            >
              {/* Status dot */}
              <span className="relative flex-shrink-0">
                <span
                  className={`block w-1.5 h-1.5 sm:w-[5px] sm:h-[5px] rounded-full transition-colors duration-300 ${
                    isActive
                      ? "bg-[var(--accent-cyan)]"
                      : isPast
                      ? "bg-[var(--accent-emerald)]"
                      : "bg-[var(--text-tertiary)]"
                  }`}
                />
                {isActive && (
                  <span className="absolute inset-0 w-1.5 h-1.5 sm:w-[5px] sm:h-[5px] rounded-full bg-[var(--accent-cyan)] animate-ping opacity-30" />
                )}
              </span>

              {/* Number */}
              <span className={`text-[0.5rem] sm:text-[0.55rem] tabular-nums ${isActive ? "text-[var(--accent-cyan)]" : isPast ? "text-[var(--accent-emerald)]" : ""}`}>
                {s.num}
              </span>

              {/* Label — hidden on very small screens */}
              <span className="hidden md:inline tracking-wider">{s.label}</span>
            </button>

            {/* Connector with progress line */}
            {i < STAGES.length - 1 && (
              <div className="relative w-5 sm:w-8 h-px mx-0.5">
                <div className="absolute inset-0 bg-[var(--text-tertiary)] opacity-15" />
                {isPast && (
                  <div className="absolute inset-0 bg-[var(--accent-emerald)] opacity-50 origin-left" />
                )}
                {isActive && (
                  <div
                    className="absolute inset-0 bg-[var(--accent-cyan)] opacity-40 origin-left"
                    style={{ transform: `scaleX(${currentIdx === sIdx ? 0.5 : 0})` }}
                  />
                )}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}
