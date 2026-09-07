"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { apiRequest, qs } from "@/lib/api";

interface AuditEntry {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  user_id: number | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

interface SecurityEvent {
  id: number;
  event_type: string;
  severity: string;
  description: string | null;
  source: string | null;
  created_at: string;
}

interface ImportLog {
  id: number;
  import_type: string;
  filename: string | null;
  status: string;
  records_imported: number;
  records_failed: number;
  created_at: string;
}

export default function AuditPage() {
  const [activeTab, setActiveTab] = useState<"events" | "imports" | "security">("events");
  const [securityEvents, setSecurityEvents] = useState<SecurityEvent[]>([]);
  const [importLogs, setImportLogs] = useState<ImportLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSecurityEvents = useCallback(async () => {
    try {
      const data = await apiRequest<{ items: SecurityEvent[] }>(
        "/api/v1/security-events?page_size=100"
      );
      setSecurityEvents(data.items || []);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const loadImportLogs = useCallback(async () => {
    try {
      const data = await apiRequest<{ items: ImportLog[] }>(
        "/api/v1/import/audit-logs?page_size=100"
      );
      setImportLogs(data.items || []);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    Promise.all([loadSecurityEvents(), loadImportLogs()]).finally(() => setLoading(false));
  }, [loadSecurityEvents, loadImportLogs]);

  const severityColor = (s: string) => {
    switch (s) {
      case "CRITICAL": return "danger";
      case "HIGH": return "danger";
      case "MEDIUM": return "warning";
      case "LOW": return "info";
      default: return "neutral";
    }
  };

  return (
    <div className="eg-page">
      <div className="eg-page-header">
        <Link href="/dashboard" className="eg-breadcrumb">← Dashboard</Link>
        <h1 className="eg-page-title">Audit Trail</h1>
        <p className="eg-page-desc">System events, imports, and security activity.</p>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: "0.25rem", marginBottom: "1.5rem" }}>
        {[
          { key: "events" as const, label: "Security Events" },
          { key: "imports" as const, label: "Import History" },
          { key: "security" as const, label: "System Activity" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: "0.5rem 1rem",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: activeTab === tab.key ? "var(--accent)" : "transparent",
              color: activeTab === tab.key ? "#fff" : "var(--text-muted)",
              fontSize: "0.8125rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="eg-alert eg-alert-danger" style={{ marginBottom: "1rem" }}>{error}</div>
      )}

      {loading ? (
        <p style={{ color: "var(--text-muted)", padding: "2rem" }}>Loading...</p>
      ) : (
        <>
          {/* Security Events Tab */}
          {activeTab === "events" && (
            <div className="glass" style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
              {securityEvents.length === 0 ? (
                <div style={{ padding: "3rem", textAlign: "center" }}>
                  <p style={{ color: "var(--text-muted)" }}>No security events recorded.</p>
                </div>
              ) : (
                <div className="eg-table-wrap" style={{ border: "none", borderRadius: 0, boxShadow: "none" }}>
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Severity</th>
                        <th>Source</th>
                        <th>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {securityEvents.map((e) => (
                        <tr key={e.id}>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", whiteSpace: "nowrap" }}>
                            {new Date(e.created_at).toLocaleString()}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{e.event_type}</td>
                          <td>
                            <span className={`eg-badge eg-badge-${severityColor(e.severity)}`}>
                              {e.severity}
                            </span>
                          </td>
                          <td style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>{e.source || "—"}</td>
                          <td style={{ fontSize: "0.8125rem" }}>{e.description || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Import History Tab */}
          {activeTab === "imports" && (
            <div className="glass" style={{ borderRadius: "var(--radius-lg)", overflow: "hidden" }}>
              {importLogs.length === 0 ? (
                <div style={{ padding: "3rem", textAlign: "center" }}>
                  <p style={{ color: "var(--text-muted)" }}>No import history.</p>
                  <Link href="/import" className="eg-btn eg-btn-primary" style={{ marginTop: "1rem" }}>Import Data</Link>
                </div>
              ) : (
                <div className="eg-table-wrap" style={{ border: "none", borderRadius: 0, boxShadow: "none" }}>
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>File</th>
                        <th>Status</th>
                        <th>Imported</th>
                        <th>Failed</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importLogs.map((log) => (
                        <tr key={log.id}>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.6875rem", whiteSpace: "nowrap" }}>
                            {new Date(log.created_at).toLocaleString()}
                          </td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem" }}>{log.import_type}</td>
                          <td style={{ fontSize: "0.8125rem" }}>{log.filename || "—"}</td>
                          <td>
                            <span className={`eg-badge eg-badge-${log.status === "COMPLETED" ? "success" : log.status === "FAILED" ? "danger" : "info"}`}>
                              {log.status}
                            </span>
                          </td>
                          <td style={{ fontSize: "0.875rem" }}>{log.records_imported}</td>
                          <td style={{ fontSize: "0.875rem", color: log.records_failed > 0 ? "var(--danger)" : "var(--text-muted)" }}>
                            {log.records_failed}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* System Activity Tab */}
          {activeTab === "security" && (
            <div className="glass" style={{ padding: "2rem", borderRadius: "var(--radius-lg)" }}>
              <h3 style={{ fontFamily: "var(--font-display)", fontSize: "1rem", marginBottom: "1rem" }}>System Activity</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Audit trail for all system operations. Each entry records the action, entity, user, and timestamp.
              </p>
              <div style={{ marginTop: "1.5rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                {securityEvents.slice(0, 20).map((e) => (
                  <div key={e.id} style={{ display: "flex", alignItems: "start", gap: "0.75rem", padding: "0.75rem", background: "var(--bg-glass)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
                    <span className={`eg-badge eg-badge-${severityColor(e.severity)}`} style={{ flexShrink: 0 }}>
                      {e.severity}
                    </span>
                    <div style={{ flex: 1 }}>
                      <p style={{ fontSize: "0.8125rem", fontWeight: 500 }}>{e.event_type}</p>
                      <p style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{e.description || "No description"}</p>
                    </div>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.625rem", color: "var(--text-faint)", whiteSpace: "nowrap" }}>
                      {new Date(e.created_at).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
