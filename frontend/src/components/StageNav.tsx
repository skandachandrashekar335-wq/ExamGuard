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
    <nav className="flex items-center gap-1" role="navigation" aria-label="Verification stages">
      {STAGES.map((s, i) => {
        const sIdx = STAGE_ORDER.indexOf(s.id);
        const isActive = s.id === stage;
        const isPast = currentIdx > sIdx;

        return (
          <button
            key={s.id}
            onClick={() => onStageClick(s.id)}
            className={`eg-focusable flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono transition-all duration-300 ${
              isActive
                ? "bg-[rgba(0,229,255,0.1)] text-[var(--accent-cyan)] border border-[rgba(0,229,255,0.3)]"
                : isPast
                ? "text-[var(--accent-emerald)] border border-transparent hover:bg-white/5"
                : "text-[var(--text-tertiary)] border border-transparent hover:bg-white/5"
            }`}
            aria-current={isActive ? "step" : undefined}
          >
            <span className={`text-[0.6rem] ${isActive ? "text-[var(--accent-cyan)]" : isPast ? "text-[var(--accent-emerald)]" : "text-[var(--text-tertiary)]"}`}>
              {s.num}
            </span>
            <span className="hidden sm:inline">{s.label}</span>
            {i < STAGES.length - 1 && (
              <span className={`ml-1 ${isPast ? "text-[var(--accent-emerald)]" : "text-[var(--text-tertiary)]"}`}>→</span>
            )}
          </button>
        );
      })}
    </nav>
  );
}
