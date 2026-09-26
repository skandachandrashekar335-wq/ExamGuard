"use client";

import type { IdentityVerificationEvidence } from "@/lib/types";

const SIGNAL_META: Record<
  string,
  { label: string; category: "IDENTITY" | "LIVENESS" | "SUPPORTING"; note?: string }
> = {
  similarity_score: {
    label: "Face Similarity",
    category: "IDENTITY",
    note: "How closely the live capture matches the stored reference photo. This is a relative comparison score, not a probability.",
  },
  liveness: {
    label: "Live-Person Check",
    category: "LIVENESS",
    note: "Confirms a real person is in front of the camera - not a photo or a screen replay.",
  },
  liveness_score: {
    label: "Live-Person Check Score",
    category: "LIVENESS",
    note: "Supporting score behind the live-person check.",
  },
  liveness_signal: {
    label: "Live-Person Check",
    category: "LIVENESS",
    note: "Confirms a real person is in front of the camera - not a photo or a screen replay.",
  },
  image_quality: {
    label: "Image Quality",
    category: "SUPPORTING",
    note: "Whether the captured image was clear enough to judge.",
  },
  provider: { label: "Provider", category: "SUPPORTING" },
  failure_category: { label: "Failure Category", category: "SUPPORTING" },
};

const CATEGORY_STYLE: Record<string, { color: string; bg: string }> = {
  IDENTITY: { color: "var(--accent)", bg: "rgba(107,78,255,0.12)" },
  LIVENESS: { color: "var(--success)", bg: "rgba(45,159,111,0.12)" },
  SUPPORTING: { color: "var(--text-muted)", bg: "rgba(255,255,255,0.05)" },
};

function formatValue(signalType: string, value: string | null): string {
  if (value === null) return "—";
  if (signalType === "similarity_score" || signalType === "liveness_score") {
    const num = parseFloat(value);
    if (!isNaN(num)) return `${(num * 100).toFixed(1)}%`;
  }
  if (signalType === "liveness" || signalType === "liveness_signal") {
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

function formatDetails(details: string | null): string | null {
  if (!details) return null;
  try {
    const obj = JSON.parse(details);
    if (obj && typeof obj === "object" && !Array.isArray(obj)) {
      const parts: string[] = [];
      if (typeof obj.source === "string") parts.push(`source: ${obj.source}`);
      if (typeof obj.signal === "string") parts.push(`signal: ${obj.signal}`);
      if (typeof obj.numeric_score === "number") {
        parts.push(`score: ${obj.numeric_score.toFixed(3)}`);
      }
      if (parts.length > 0) return parts.join(" / ");
      return JSON.stringify(obj);
    }
  } catch {
    // not JSON — show as-is
  }
  return details;
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
        const meta = SIGNAL_META[e.signal_type];
        const detailsText = formatDetails(e.details);
        const label = meta?.label || e.signal_type;
        const category = meta?.category;
        const categoryStyle = category ? CATEGORY_STYLE[category] : null;
        // For score rows the confidence column repeats the displayed value;
        // only show it when it adds information (other signal types).
        const confidencePct =
          e.confidence !== null &&
          e.signal_type !== "similarity_score" &&
          e.signal_type !== "liveness_score"
            ? `${(e.confidence * 100).toFixed(1)}%`
            : null;
        return (
          <div
            key={e.id}
            className="border p-3 rounded"
            style={{ borderColor: "var(--border)", background: "var(--bg-glass-light)" }}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="eg-mono-sm text-[var(--text-secondary)]">
                {categoryStyle && (
                  <span
                    className="eg-mono-sm"
                    style={{
                      color: categoryStyle.color,
                      background: categoryStyle.bg,
                      borderRadius: "4px",
                      padding: "1px 6px",
                      marginRight: "0.5rem",
                      fontSize: "0.5625rem",
                      letterSpacing: "0.08em",
                    }}
                  >
                    {category}
                  </span>
                )}
                {label}
              </span>
              <span className="font-mono text-xs" style={{ color: "var(--text-primary)" }}>
                {formatValue(e.signal_type, e.signal_value)}
              </span>
            </div>
            {bar !== null && (
              <div className="h-1 w-full mt-1 rounded" style={{ background: "var(--border)" }}>
                <div
                  className="h-full bg-[var(--accent)] transition-all duration-300 rounded"
                  style={{ width: `${bar}%` }}
                />
              </div>
            )}
            {meta?.note && (
              <p className="text-xs text-[var(--text-muted)] mt-1">{meta.note}</p>
            )}
            {confidencePct && (
              <span className="eg-mono-sm text-[var(--text-muted)] mt-1 block">
                confidence: {confidencePct}
              </span>
            )}
            {detailsText && (
              <p className="text-xs text-[var(--text-muted)] mt-1 break-words">
                {detailsText}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
