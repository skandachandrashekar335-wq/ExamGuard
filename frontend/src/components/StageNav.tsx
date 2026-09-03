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
    <nav className="flex items-center gap-0.5 sm:gap-1" role="navigation" aria-label="Verification stages">
      {STAGES.map((s, i) => {
        const sIdx = STAGE_ORDER.indexOf(s.id);
        const isActive = s.id === stage;
        const isPast = currentIdx > sIdx;
        const isNext = currentIdx === sIdx - 1;

        return (
          <button
            key={s.id}
            onClick={() => onStageClick(s.id)}
            className={`eg-focusable relative flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg text-[0.65rem] sm:text-xs font-mono transition-all duration-300 ${
              isActive
                ? "bg-[rgba(0,229,255,0.08)] text-[var(--accent-cyan)] border border-[rgba(0,229,255,0.25)]"
                : isPast
                ? "text-[var(--accent-emerald)] border border-transparent hover:bg-white/[0.03]"
                : isNext
                ? "text-[var(--text-tertiary)] border border-transparent hover:bg-white/[0.03] hover:text-[var(--text-secondary)]"
                : "text-[var(--text-tertiary)] border border-transparent opacity-40 hover:opacity-60"
            }`}
            aria-current={isActive ? "step" : undefined}
          >
            {/* Status dot */}
            <span className="relative flex-shrink-0">
              <span
                className={`block w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full ${
                  isActive
                    ? "bg-[var(--accent-cyan)]"
                    : isPast
                    ? "bg-[var(--accent-emerald)]"
                    : "bg-[var(--text-tertiary)]"
                }`}
              />
              {isActive && (
                <span className="absolute inset-0 w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full bg-[var(--accent-cyan)] animate-ping opacity-40" />
              )}
            </span>

            {/* Number */}
            <span className={`text-[0.55rem] sm:text-[0.6rem] ${isActive ? "text-[var(--accent-cyan)]" : isPast ? "text-[var(--accent-emerald)]" : ""}`}>
              {s.num}
            </span>

            {/* Label — hidden on very small screens */}
            <span className="hidden sm:inline tracking-wider">{s.label}</span>

            {/* Connector */}
            {i < STAGES.length - 1 && (
              <span className={`ml-0.5 ${isPast ? "text-[var(--accent-emerald)] opacity-60" : "text-[var(--text-tertiary)] opacity-30"}`}>
                —
              </span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
