"use client";

import type { IdentityVerificationEvidence } from "@/lib/types";

const SIGNAL_LABELS: Record<string, string> = {
  similarity_score: "Identity Match",
  liveness_score: "Liveness Score",
  liveness_signal: "Liveness Result",
  image_quality: "Image Quality",
  provider: "Provider",
  failure_category: "Failure Category",
};

function formatValue(signalType: string, value: string | null): string {
  if (value === null) return "—";
  if (signalType === "similarity_score" || signalType === "liveness_score") {
    const num = parseFloat(value);
    if (!isNaN(num)) return `${(num * 100).toFixed(1)}%`;
  }
  if (signalType === "liveness_signal") {
    return value === "PASS" ? "PASS" : value === "FAIL" ? "FAIL" : value;
  }
  return value;
}

function signalBar(signalType: string, value: string | null): number | null {
  if (signalType !== "similarity_score" && signalType !== "liveness_score")
    return null;
  const num = parseFloat(value || "");
  if (isNaN(num)) return null;
  return Math.max(0, Math.min(100, num * 100));
}

interface Props {
  evidence: IdentityVerificationEvidence[];
}

export default function EvidenceDisplay({ evidence }: Props) {
  if (evidence.length === 0) {
    return (
      <p className="eg-mono text-[var(--text-muted)] text-[10px]">
        No evidence recorded
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {evidence.map((e) => {
        const bar = signalBar(e.signal_type, e.signal_value);
        const label = SIGNAL_LABELS[e.signal_type] || e.signal_type;
        return (
          <div key={e.id} className="border border-white/5 bg-black p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="eg-mono-sm text-[var(--text-secondary)]">
                {label}
              </span>
              <span className="font-mono text-xs text-white">
                {formatValue(e.signal_type, e.signal_value)}
              </span>
            </div>
            {bar !== null && (
              <div className="h-1 bg-white/5 w-full mt-1">
                <div
                  className="h-full bg-white/40 transition-all duration-300"
                  style={{ width: `${bar}%` }}
                />
              </div>
            )}
            {e.confidence !== null && (
              <span className="eg-mono-sm text-[var(--text-muted)] mt-1 block">
                confidence: {(e.confidence * 100).toFixed(1)}%
              </span>
            )}
            {e.details && (
              <p className="text-xs text-[var(--text-muted)] mt-1">
                {e.details}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
