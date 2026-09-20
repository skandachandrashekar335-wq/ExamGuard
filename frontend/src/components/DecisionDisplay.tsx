"use client";

import type { VerificationDecision } from "@/lib/types";

const DECISION_STYLES: Record<string, { label: string; border: string; text: string }> = {
  PENDING: { label: "Pending", border: "border-[var(--border)]", text: "text-[var(--text-secondary)]" },
  MATCH: { label: "Match", border: "border-[var(--success)]", text: "text-[var(--success)]" },
  NO_MATCH: { label: "No Match", border: "border-[var(--danger)]", text: "text-[var(--danger)]" },
  INCONCLUSIVE: { label: "Inconclusive", border: "border-[var(--warning)]", text: "text-[var(--warning)]" },
};

interface Props {
  decision: string;
  failureReason: string | null;
}

export default function DecisionDisplay({ decision, failureReason }: Props) {
  const style = DECISION_STYLES[decision] || DECISION_STYLES.PENDING;

  return (
    <div className={`glass-surface border ${style.border} p-4 rounded`}>
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
