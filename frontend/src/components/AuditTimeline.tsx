"use client";

import type {
  IdentityVerificationAttempt,
  IdentityVerificationEvidence,
} from "@/lib/types";

interface Props {
  attempt: IdentityVerificationAttempt;
  evidence: IdentityVerificationEvidence[];
}

interface TimelineEntry {
  time: string;
  label: string;
  detail?: string;
}

export default function AuditTimeline({ attempt, evidence }: Props) {
  const entries: TimelineEntry[] = [];

  entries.push({
    time: attempt.created_at,
    label: "Verification created",
    detail: `Method: ${attempt.verification_method}`,
  });

  if (attempt.started_at) {
    entries.push({
      time: attempt.started_at,
      label: "Verification started",
    });
  }

  for (const e of evidence) {
    entries.push({
      time: e.created_at,
      label: `Evidence: ${e.signal_type}`,
      detail: e.signal_value || undefined,
    });
  }

  if (attempt.completed_at) {
    entries.push({
      time: attempt.completed_at,
      label: `Decision: ${attempt.decision}`,
      detail: attempt.failure_reason || undefined,
    });
  }

  if (attempt.failure_reason && attempt.status === "COMPLETED") {
    const parsed = parseOverrideAudit(attempt.failure_reason);
    if (parsed) {
      entries.push({
        time: parsed.timestamp,
        label: "Human override",
        detail: `${parsed.original_decision} → ${parsed.override_decision}: ${parsed.reason}`,
      });
    }
  }

  entries.sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

  if (entries.length === 0) {
    return (
      <p className="eg-mono text-[var(--text-muted)] text-[10px]">
        No audit entries
      </p>
    );
  }

  return (
    <div className="space-y-0">
      {entries.map((entry, i) => (
        <div key={i} className="flex gap-3 relative">
          <div className="flex flex-col items-center">
            <div className="w-1.5 h-1.5 bg-white/30 mt-1.5 shrink-0" />
            {i < entries.length - 1 && (
              <div className="w-px flex-1 bg-white/10" />
            )}
          </div>
          <div className="pb-4">
            <span className="eg-mono-sm text-[var(--text-secondary)] block">
              {entry.label}
            </span>
            {entry.detail && (
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                {entry.detail}
              </p>
            )}
            <span className="text-[10px] text-[var(--text-muted)] font-mono mt-0.5 block">
              {new Date(entry.time).toLocaleString()}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

function parseOverrideAudit(
  reason: string,
): { original_decision: string; override_decision: string; reason: string; timestamp: string } | null {
  try {
    const parsed = JSON.parse(reason);
    if (parsed.original_decision && parsed.override_decision) {
      return parsed;
    }
  } catch {
    // not JSON
  }
  return null;
}
