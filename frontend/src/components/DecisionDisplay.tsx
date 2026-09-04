"use client";

import type { VerificationDecision } from "@/lib/types";

const DECISION_STYLES: Record<string, { label: string; border: string; text: string }> = {
  PENDING: { label: "Pending", border: "border-white/20", text: "text-[var(--text-secondary)]" },
  MATCH: { label: "Match", border: "border-white/40", text: "text-white" },
  NO_MATCH: { label: "No Match", border: "border-white/40", text: "text-[var(--text-secondary)]" },
  INCONCLUSIVE: { label: "Inconclusive", border: "border-white/20", text: "text-[var(--text-secondary)]" },
};

interface Props {
  decision: string;
  failureReason: string | null;
}

export default function DecisionDisplay({ decision, failureReason }: Props) {
  const style = DECISION_STYLES[decision] || DECISION_STYLES.PENDING;

  return (
    <div className={`border ${style.border} p-4`}>
      <span className="eg-mono-sm text-[var(--text-muted)] block mb-2">
        Decision
      </span>
      <span className={`font-mono text-lg ${style.text}`}>{style.label}</span>
      {failureReason && (
        <p className="text-xs text-[var(--text-muted)] mt-2 break-words">
          {failureReason}
        </p>
      )}
    </div>
  );
}
