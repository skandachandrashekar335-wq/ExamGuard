"use client";

import type { VerificationDecision } from "@/lib/types";

const DECISION_STYLES: Record<string, { label: string; border: string; text: string }> = {
  PENDING: { label: "Pending", border: "border-[var(--border)]", text: "text-[var(--text-secondary)]" },
  MATCH: { label: "Match", border: "border-[var(--success)]", text: "text-[var(--success)]" },
  NO_MATCH: { label: "No Match", border: "border-[var(--danger)]", text: "text-[var(--danger)]" },
  INCONCLUSIVE: { label: "Identity Review Required", border: "border-[var(--warning)]", text: "text-[var(--warning)]" },
};

const DECISION_HINTS: Record<string, string> = {
  MATCH:
    "Face similarity met the acceptance threshold and image quality was acceptable.",
  NO_MATCH:
    "The evidence did not meet the acceptance policy — for example a live-person check failure, or face similarity below the acceptance threshold.",
  INCONCLUSIVE:
    "The automatic check could not confirm identity. An invigilator must review this check-in and record CHECK IN or CHECK OUT with a reason.",
};

interface Props {
  decision: string;
  failureReason: string | null;
}

export default function DecisionDisplay({ decision, failureReason }: Props) {
  const style = DECISION_STYLES[decision] || DECISION_STYLES.PENDING;
  const hint = DECISION_HINTS[decision];

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
      {!failureReason && hint && (
        <p className="text-xs text-[var(--text-muted)] mt-2">{hint}</p>
      )}
    </div>
  );
}
