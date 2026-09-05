"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listSecurityEvents,
  type SecurityEvent,
} from "@/lib/security-event-api";

const EVENT_TYPES = [
  "SIGNAL_DETECTED",
  "RISK_THRESHOLD_EXCEEDED",
  "ENTRY_ESCALATED",
  "DUPLICATE_ENTRY_DETECTED",
  "IDENTITY_MISMATCH_DETECTED",
  "MANUAL_FLAG",
  "ATTENDANCE_CORRECTED",
  "CAMERA_OFFLINE_DURING_EXAM",
  "UNUSUAL_PATTERN",
  "PROXY_RISK_CRITICAL",
];

const SEVERITIES = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

function severityClass(s: string): string {
  if (s === "CRITICAL") return "text-white font-bold";
  if (s === "HIGH") return "text-[var(--gray-200)]";
  if (s === "MEDIUM") return "text-[var(--gray-300)]";
  if (s === "LOW") return "text-[var(--gray-400)]";
  return "text-[var(--text-muted)]";
}

export default function SecurityEventsPage() {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filterType, setFilterType] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const [filterSource, setFilterSource] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listSecurityEvents({
        page,
        page_size: pageSize,
        event_type: filterType || undefined,
        severity: filterSeverity || undefined,
        source: filterSource || undefined,
      });
      setEvents(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load security events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, filterType, filterSeverity, filterSource]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <Link
          href="/dashboard"
          className="eg-mono-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] mb-8 inline-block"
        >
          &larr; DASHBOARD
        </Link>

        <h1 className="eg-display text-3xl mb-2">SECURITY EVENTS</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Persistent, immutable audit record of security-relevant activity.
        </p>

        {/* Filters */}
        <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-4 mb-6">
          <div className="eg-mono-sm text-[var(--text-muted)] mb-3">FILTERS</div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">TYPE</label>
              <select
                value={filterType}
                onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
                className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5"
              >
                <option value="">ALL</option>
                {EVENT_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">SEVERITY</label>
              <select
                value={filterSeverity}
                onChange={(e) => { setFilterSeverity(e.target.value); setPage(1); }}
                className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5"
              >
                <option value="">ALL</option>
                {SEVERITIES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">SOURCE</label>
              <input
                type="text"
                value={filterSource}
                onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}
                placeholder="Any"
                className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5 placeholder:text-[var(--text-muted)]"
              />
            </div>
          </div>
        </div>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-[var(--text-muted)]">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">Loading security events...</span>
          </div>
        ) : events.length === 0 ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-1">NO SECURITY EVENTS</h3>
            <p className="text-sm text-[var(--text-muted)]">No security events have been recorded.</p>
          </div>
        ) : (
          <>
            <div className="border border-white/[0.06] bg-[var(--bg-surface)]">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  {total} EVENTS
                </span>
              </div>
              <div className="divide-y divide-white/[0.04]">
                {events.map((evt) => (
                  <div key={evt.id} className="px-4 py-3 flex items-start gap-4">
                    <span className={`eg-mono-sm shrink-0 w-20 ${severityClass(evt.severity)}`}>
                      {evt.severity}
                    </span>
                    <span className="eg-mono-sm shrink-0 w-48 text-[var(--text-secondary)]">
                      {evt.event_type}
                    </span>
                    <span className="eg-mono-sm flex-1 text-[var(--text-secondary)]">
                      {evt.entity_type} #{evt.entity_id}
                    </span>
                    <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                      {evt.source}
                    </span>
                    <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                      {new Date(evt.created_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {totalPages > 1 && (
              <div className="flex justify-between items-center mt-4">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="eg-btn disabled:opacity-30"
                >
                  PREVIOUS
                </button>
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  PAGE {page} OF {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="eg-btn disabled:opacity-30"
                >
                  NEXT
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
