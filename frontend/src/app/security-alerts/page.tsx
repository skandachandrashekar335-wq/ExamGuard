"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
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
  if (s === "CRITICAL") return "eg-badge eg-badge-danger";
  if (s === "HIGH") return "eg-badge eg-badge-danger";
  if (s === "MEDIUM") return "eg-badge eg-badge-warning";
  if (s === "LOW") return "eg-badge eg-badge-info";
  return "eg-badge eg-badge-neutral";
}

function statusClass(s: string): string {
  if (s === "OPEN") return "eg-badge eg-badge-warning";
  if (s === "ACKNOWLEDGED") return "eg-badge eg-badge-info";
  if (s === "RESOLVED") return "eg-badge eg-badge-success";
  return "eg-badge eg-badge-neutral";
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
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Security Alerts</h1>
          <p className="eg-page-desc">
            Operational alerts from security events. Acknowledge, resolve, or dismiss.
          </p>
        </div>

        <div className="eg-filter-bar">
          <div>
            <label className="eg-label">Status</label>
            <select
              value={filterStatus}
              onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
              className="eg-select"
            >
              <option value="">All</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
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
        </div>

        {error && (
          <div className="glass-surface" style={{ padding: "1rem", marginBottom: "1.5rem", borderColor: "var(--danger)" }}>
            <span className="eg-mono" style={{ color: "var(--danger)" }}>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface" style={{ padding: "3rem", textAlign: "center" }}>
            <span className="eg-mono" style={{ color: "var(--text-muted)" }}>Loading security alerts...</span>
          </div>
        ) : alerts.length === 0 ? (
          <div className="glass-surface">
            <div className="eg-empty">
              <h3 className="eg-empty-title">No Security Alerts</h3>
              <p className="eg-empty-desc">No alerts match the current filters.</p>
            </div>
          </div>
        ) : (
          <>
            <div className="glass-surface" style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
              {alerts.map((alert) => (
                <div
                  key={alert.id}
                  style={{
                    padding: "1rem 1.25rem",
                    borderBottom: "1px solid var(--border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", flexWrap: "wrap" }}>
                    <span className={severityClass(alert.severity)}>
                      {alert.severity}
                    </span>
                    <span className={statusClass(alert.status)}>
                      {alert.status}
                    </span>
                    <span className="eg-mono-sm" style={{ flex: 1, color: "var(--text-secondary)" }}>
                      {alert.message}
                    </span>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>
                      {new Date(alert.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div style={{ marginTop: "0.5rem", display: "flex", alignItems: "center", gap: "0.75rem", fontSize: "0.75rem" }}>
                    <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>
                      EVENT #{alert.security_event_id}
                    </span>
                    {alert.assigned_to && (
                      <span className="eg-mono-sm" style={{ color: "var(--text-muted)" }}>
                        ASSIGNED: {alert.assigned_to}
                      </span>
                    )}
                    {alert.status === "OPEN" && (
                      <div style={{ display: "flex", gap: "0.5rem", marginLeft: "auto" }}>
                        <button
                          onClick={() => handleAcknowledge(alert.id)}
                          disabled={actionLoading === alert.id}
                          className="eg-btn"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}
                        >
                          Acknowledge
                        </button>
                        <button
                          onClick={() => handleResolve(alert.id)}
                          disabled={actionLoading === alert.id}
                          className="eg-btn"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}
                        >
                          Resolve
                        </button>
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          disabled={actionLoading === alert.id}
                          className="eg-btn eg-btn-danger"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                    {alert.status === "ACKNOWLEDGED" && (
                      <div style={{ display: "flex", gap: "0.5rem", marginLeft: "auto" }}>
                        <button
                          onClick={() => handleResolve(alert.id)}
                          disabled={actionLoading === alert.id}
                          className="eg-btn"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}
                        >
                          Resolve
                        </button>
                        <button
                          onClick={() => handleDismiss(alert.id)}
                          disabled={actionLoading === alert.id}
                          className="eg-btn eg-btn-danger"
                          style={{ fontSize: "0.75rem", padding: "0.25rem 0.625rem" }}
                        >
                          Dismiss
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
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
