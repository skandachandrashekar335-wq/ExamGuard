"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listSecurityAlerts,
  acknowledgeAlert,
  resolveAlert,
  dismissAlert,
  type SecurityAlert,
} from "@/lib/security-alert-api";

const STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"];
const SEVERITIES = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"];

function severityClass(s: string): string {
  if (s === "CRITICAL") return "text-white font-bold";
  if (s === "HIGH") return "text-[var(--gray-200)]";
  if (s === "MEDIUM") return "text-[var(--gray-300)]";
  if (s === "LOW") return "text-[var(--gray-400)]";
  return "text-[var(--text-muted)]";
}

function statusClass(s: string): string {
  if (s === "OPEN") return "border border-white/20 px-2 py-0.5";
  if (s === "ACKNOWLEDGED") return "border border-white/10 px-2 py-0.5";
  if (s === "RESOLVED") return "border border-white/[0.06] px-2 py-0.5 text-[var(--text-muted)]";
  return "border border-white/[0.06] px-2 py-0.5 text-[var(--text-muted)]";
}

export default function SecurityAlertsPage() {
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const [filterStatus, setFilterStatus] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listSecurityAlerts({
        page,
        page_size: pageSize,
        status: filterStatus || undefined,
        severity: filterSeverity || undefined,
      });
      setAlerts(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load security alerts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, filterStatus, filterSeverity]);

  const handleAcknowledge = async (id: number) => {
    setActionLoading(id);
    try {
      await acknowledgeAlert(id);
      await fetchData();
    } catch {
      setError("Failed to acknowledge alert");
    } finally {
      setActionLoading(null);
    }
  };

  const handleResolve = async (id: number) => {
    setActionLoading(id);
    try {
      await resolveAlert(id);
      await fetchData();
    } catch {
      setError("Failed to resolve alert");
    } finally {
      setActionLoading(null);
    }
  };

  const handleDismiss = async (id: number) => {
    const reason = window.prompt("Reason for dismissing this alert:");
    if (reason === null) return;
    setActionLoading(id);
    try {
      await dismissAlert(id, reason || "No reason provided");
      await fetchData();
    } catch {
      setError("Failed to dismiss alert");
    } finally {
      setActionLoading(null);
    }
  };

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

        <h1 className="eg-display text-3xl mb-2">SECURITY ALERTS</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Operational alerts from security events. Acknowledge, resolve, or dismiss.
        </p>

        {/* Filters */}
        <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-4 mb-6">
          <div className="eg-mono-sm text-[var(--text-muted)] mb-3">FILTERS</div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="eg-mono-sm text-[var(--text-muted)] block mb-1">STATUS</label>
              <select
                value={filterStatus}
                onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
                className="w-full bg-[var(--bg-raised)] border border-white/[0.08] text-[var(--text-secondary)] eg-mono-sm px-2 py-1.5"
              >
                <option value="">ALL</option>
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{s}</option>
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
          </div>
        </div>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-[var(--text-muted)]">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">Loading security alerts...</span>
          </div>
        ) : alerts.length === 0 ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-1">NO SECURITY ALERTS</h3>
            <p className="text-sm text-[var(--text-muted)]">No alerts match the current filters.</p>
          </div>
        ) : (
          <>
            <div className="border border-white/[0.06] bg-[var(--bg-surface)]">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  {total} ALERTS
                </span>
              </div>
              <div className="divide-y divide-white/[0.04]">
                {alerts.map((alert) => (
                  <div key={alert.id} className="px-4 py-3">
                    <div className="flex items-start gap-4">
                      <span className={`eg-mono-sm shrink-0 w-20 ${severityClass(alert.severity)}`}>
                        {alert.severity}
                      </span>
                      <span className={`eg-mono-sm shrink-0 ${statusClass(alert.status)}`}>
                        {alert.status}
                      </span>
                      <span className="eg-mono-sm flex-1 text-[var(--text-secondary)]">
                        {alert.message}
                      </span>
                      <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                        {new Date(alert.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-xs">
                      <span className="eg-mono-sm text-[var(--text-muted)]">
                        EVENT #{alert.security_event_id}
                      </span>
                      {alert.assigned_to && (
                        <span className="eg-mono-sm text-[var(--text-muted)]">
                          ASSIGNED: {alert.assigned_to}
                        </span>
                      )}
                      {alert.status === "OPEN" && (
                        <div className="flex gap-2 ml-auto">
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            disabled={actionLoading === alert.id}
                            className="eg-btn text-xs"
                          >
                            ACKNOWLEDGE
                          </button>
                          <button
                            onClick={() => handleResolve(alert.id)}
                            disabled={actionLoading === alert.id}
                            className="eg-btn text-xs"
                          >
                            RESOLVE
                          </button>
                          <button
                            onClick={() => handleDismiss(alert.id)}
                            disabled={actionLoading === alert.id}
                            className="eg-btn text-xs"
                          >
                            DISMISS
                          </button>
                        </div>
                      )}
                      {alert.status === "ACKNOWLEDGED" && (
                        <div className="flex gap-2 ml-auto">
                          <button
                            onClick={() => handleResolve(alert.id)}
                            disabled={actionLoading === alert.id}
                            className="eg-btn text-xs"
                          >
                            RESOLVE
                          </button>
                          <button
                            onClick={() => handleDismiss(alert.id)}
                            disabled={actionLoading === alert.id}
                            className="eg-btn text-xs"
                          >
                            DISMISS
                          </button>
                        </div>
                      )}
                    </div>
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
