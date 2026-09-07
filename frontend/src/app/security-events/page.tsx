"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
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
  if (s === "CRITICAL") return "eg-badge eg-badge-danger";
  if (s === "HIGH") return "eg-badge eg-badge-danger";
  if (s === "MEDIUM") return "eg-badge eg-badge-warning";
  if (s === "LOW") return "eg-badge eg-badge-info";
  return "eg-badge eg-badge-neutral";
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
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Security Events</h1>
          <p className="eg-page-desc">
            Persistent, immutable audit record of security-relevant activity.
          </p>
        </div>

        <div className="eg-filter-bar">
          <div>
            <label className="eg-label">Type</label>
            <select
              value={filterType}
              onChange={(e) => { setFilterType(e.target.value); setPage(1); }}
              className="eg-select"
            >
              <option value="">All</option>
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="eg-label">Severity</label>
            <select
              value={filterSeverity}
              onChange={(e) => { setFilterSeverity(e.target.value); setPage(1); }}
              className="eg-select"
            >
              <option value="">All</option>
              {SEVERITIES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="eg-label">Source</label>
            <input
              type="text"
              value={filterSource}
              onChange={(e) => { setFilterSource(e.target.value); setPage(1); }}
              placeholder="Any"
              className="eg-input"
            />
          </div>
        </div>

        {error && (
          <div className="glass-surface" style={{ padding: "1rem", marginBottom: "1.5rem", borderColor: "var(--danger)" }}>
            <span className="eg-mono" style={{ color: "var(--danger)" }}>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface" style={{ padding: "3rem", textAlign: "center" }}>
            <span className="eg-mono" style={{ color: "var(--text-muted)" }}>Loading security events...</span>
          </div>
        ) : events.length === 0 ? (
          <div className="glass-surface">
            <div className="eg-empty">
              <h3 className="eg-empty-title">No Security Events</h3>
              <p className="eg-empty-desc">No security events have been recorded.</p>
            </div>
          </div>
        ) : (
          <>
            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Event Type</th>
                    <th>Entity</th>
                    <th>Source</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((evt) => (
                    <tr key={evt.id}>
                      <td>
                        <span className={severityClass(evt.severity)}>
                          {evt.severity}
                        </span>
                      </td>
                      <td>{evt.event_type}</td>
                      <td>{evt.entity_type} #{evt.entity_id}</td>
                      <td>{evt.source}</td>
                      <td>{new Date(evt.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="eg-pagination">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="eg-btn disabled:opacity-30"
                >
                  Previous
                </button>
                <span className="eg-pagination-info">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="eg-btn disabled:opacity-30"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
