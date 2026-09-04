"use client";

import { useState } from "react";

interface Props {
  currentDecision: string;
  onConfirm: (newDecision: string, reason: string) => Promise<void>;
  onCancel: () => void;
}

const DECISIONS = ["MATCH", "NO_MATCH", "INCONCLUSIVE"];

export default function OverrideDialog({
  currentDecision,
  onConfirm,
  onCancel,
}: Props) {
  const [newDecision, setNewDecision] = useState(
    DECISIONS.find((d) => d !== currentDecision) || "MATCH",
  );
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!reason.trim()) {
      setError("Reason is required");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      await onConfirm(newDecision, reason.trim());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Override failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="border border-white/20 p-4 bg-[#0a0a0a]">
      <h4 className="eg-mono-sm text-[var(--text-secondary)] mb-3">
        Human Override
      </h4>

      <div className="space-y-3">
        <div>
          <span className="eg-mono-sm text-[var(--text-muted)] block mb-1">
            Current decision
          </span>
          <span className="font-mono text-sm">{currentDecision}</span>
        </div>

        <div>
          <span className="eg-mono-sm text-[var(--text-muted)] block mb-1">
            New decision
          </span>
          <div className="flex gap-2">
            {DECISIONS.map((d) => (
              <button
                key={d}
                onClick={() => setNewDecision(d)}
                disabled={submitting}
                className={`eg-btn px-3 py-1 text-[10px] disabled:opacity-30 ${
                  newDecision === d ? "border-white text-white" : ""
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="eg-mono-sm text-[var(--text-muted)] block mb-1">
            Reason (required)
          </span>
          <textarea
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              setError("");
            }}
            disabled={submitting}
            rows={3}
            className="w-full bg-black border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 resize-none disabled:opacity-30"
            placeholder="Explain the reason for this override..."
          />
        </div>

        {error && (
          <p className="text-xs text-red-400">{error}</p>
        )}

        <p className="eg-mono-sm text-[var(--text-muted)]">
          This action will be recorded in the audit trail.
        </p>

        <div className="flex gap-3 pt-1">
          <button
            onClick={onCancel}
            disabled={submitting}
            className="eg-btn px-4 py-2 disabled:opacity-30"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !reason.trim()}
            className="eg-btn px-4 py-2 border-white/40 text-white disabled:opacity-30"
          >
            {submitting ? "Confirming..." : "Confirm Override"}
          </button>
        </div>
      </div>
    </div>
  );
}
