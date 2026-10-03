"use client";

import type { IdentityVerificationEvidence } from "@/lib/types";

function toPercent(value: string | null): string | null {
  if (value === null) return null;
  const num = parseFloat(value);
  if (isNaN(num)) return null;
  return `${(num * 100).toFixed(1)}%`;
}

interface Props {
  evidence: IdentityVerificationEvidence[];
}

/**
 * Two-card summary of the separate IDENTITY (face similarity) and
 * LIVENESS (live-person) checks, shown above the detailed evidence rows.
 * Renders nothing when neither signal is present.
 */
export default function CheckSummaryDisplay({ evidence }: Props) {
  const similaritySignal = evidence.find((e) => e.signal_type === "similarity_score");
  const livenessVerdict = evidence.find((e) => e.signal_type === "liveness");
  const livenessScore = evidence.find((e) => e.signal_type === "liveness_score");

  const similarity = toPercent(similaritySignal?.signal_value ?? null);
  const livenessValue = livenessVerdict?.signal_value ?? null;
  const livenessPct = toPercent(livenessScore?.signal_value ?? null);

  if (!similarity && !livenessValue && !livenessPct) return null;

  return (
    <div className="eg-grid-2">
      {similarity && (
        <div
          className="p-3 rounded"
          style={{
            border: "1px solid var(--border)",
            background: "var(--bg-glass-light)",
          }}
        >
          <span
            className="eg-mono-sm"
            style={{
              color: "var(--accent)",
              background: "rgba(107,78,255,0.12)",
              borderRadius: "4px",
              padding: "1px 6px",
              fontSize: "0.5625rem",
              letterSpacing: "0.08em",
            }}
          >
            IDENTITY
          </span>
          <p
            className="eg-mono-sm mt-2"
            style={{ color: "var(--text-secondary)" }}
          >
            Face Similarity
          </p>
          <p
            className="font-mono"
            style={{ color: "var(--text-primary)", fontSize: "1.375rem" }}
          >
            {similarity}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            Comparison with the reference photo — not a probability.
          </p>
        </div>
      )}

      {(livenessValue || livenessPct) && (
        <div
          className="p-3 rounded"
          style={{
            border: "1px solid var(--border)",
            background: "var(--bg-glass-light)",
          }}
        >
          <span
            className="eg-mono-sm"
            style={{
              color: "var(--success)",
              background: "rgba(45,159,111,0.12)",
              borderRadius: "4px",
              padding: "1px 6px",
              fontSize: "0.5625rem",
              letterSpacing: "0.08em",
            }}
          >
            LIVENESS
          </span>
          <p
            className="eg-mono-sm mt-2"
            style={{ color: "var(--text-secondary)" }}
          >
            Live-Person Check
          </p>
          <p
            className="font-mono"
            style={{
              color:
                livenessValue === "FAIL"
                  ? "var(--danger)"
                  : livenessValue === "PASS"
                    ? "var(--success)"
                    : "var(--text-primary)",
              fontSize: "1.375rem",
            }}
          >
            {livenessValue || (livenessPct ? `score ${livenessPct}` : "—")}
          </p>
          <p className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
            Confirms a real person is present — not a photo or screen replay.
            {livenessPct ? ` Supporting score: ${livenessPct}.` : ""}
          </p>
        </div>
      )}
    </div>
  );
}
