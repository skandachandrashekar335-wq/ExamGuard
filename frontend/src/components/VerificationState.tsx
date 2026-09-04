"use client";

const STATES = [
  { key: "READY", label: "Ready" },
  { key: "CAPTURING", label: "Capturing" },
  { key: "SUBMITTING", label: "Submitting" },
  { key: "VERIFYING", label: "Verifying" },
  { key: "EVALUATING", label: "Evaluating" },
  { key: "COMPLETED", label: "Completed" },
] as const;

export type VerificationUIState = (typeof STATES)[number]["key"];

interface Props {
  current: VerificationUIState;
}

export default function VerificationState({ current }: Props) {
  const currentIdx = STATES.findIndex((s) => s.key === current);

  return (
    <div className="border border-white/10 p-4">
      <span className="eg-mono-sm text-[var(--text-muted)] block mb-3">
        Verification State
      </span>
      <div className="flex items-center gap-1 flex-wrap">
        {STATES.map((s, i) => (
          <div key={s.key} className="flex items-center gap-1">
            <div
              className={`px-2 py-1 text-[10px] font-mono border ${
                i <= currentIdx
                  ? "border-white/30 text-white bg-white/5"
                  : "border-white/5 text-[var(--text-muted)]"
              }`}
            >
              {s.label}
            </div>
            {i < STATES.length - 1 && (
              <div
                className={`w-3 h-px ${
                  i < currentIdx ? "bg-white/30" : "bg-white/5"
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
