"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listSessions,
  startSession,
  endSession,
  cancelSession,
  type ExaminationSession,
} from "@/lib/session-api";
import AppShell from "@/components/AppShell";

const STATUSES = ["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "CANCELLED"];

function statusBadgeClass(s: string): string {
  if (s === "IN_PROGRESS") return "eg-badge-success";
  if (s === "NOT_STARTED") return "eg-badge-info";
  if (s === "COMPLETED") return "eg-badge-neutral";
  return "eg-badge-warning";
}

function gateBadgeClass(s: string): string {
  if (s === "GATES_OPEN") return "eg-badge-success";
  return "eg-badge-neutral";
}

export default function ExaminationSessionsPage() {
  const [sessions, setSessions] = useState<ExaminationSession[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  const [filterStatus, setFilterStatus] = useState("");

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listSessions({
        page,
        page_size: pageSize,
        status: filterStatus || undefined,
      });
      setSessions(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load sessions");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, filterStatus]);

  const handleStart = async (id: number) => {
    setActionLoading(id);
    try {
      await startSession(id);
      await fetchData();
    } catch {
      setError("Failed to start session");
    } finally {
      setActionLoading(null);
    }
  };

  const handleEnd = async (id: number) => {
    setActionLoading(id);
    try {
      await endSession(id);
      await fetchData();
    } catch {
      setError("Failed to end session");
    } finally {
      setActionLoading(null);
    }
  };

  const handleCancel = async (id: number) => {
    const reason = window.prompt("Reason for cancelling this session:");
    if (reason === null) return;
    setActionLoading(id);
    try {
      await cancelSession(id, reason || "No reason provided");
      await fetchData();
    } catch {
      setError("Failed to cancel session");
    } finally {
      setActionLoading(null);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="bg-[var(--bg-base)]">
        <div className="eg-page">
          <div className="eg-page-header">
            <Link href="/dashboard" className="eg-breadcrumb">
              &larr; Dashboard
            </Link>
            <h1 className="eg-page-title">Examination Sessions</h1>
            <p className="eg-page-desc">
              Manage session lifecycle, gate operations, and active hall monitoring.
            </p>
          </div>

          {/* Filters */}
          <div className="eg-filter-bar">
            <div className="eg-label">Filters</div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="eg-label block mb-1">Status</label>
                <select
                  value={filterStatus}
                  onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
                  className="eg-select w-full"
                >
                  <option value="">All</option>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {error && (
            <div className="glass-surface border border-[var(--border)] p-4 mb-6">
              <span className="eg-body text-[var(--text-secondary)]">{error}</span>
            </div>
          )}

          {loading ? (
            <div className="glass-surface p-12 text-center">
              <span className="eg-body text-[var(--text-muted)]">Loading sessions...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="eg-empty">
              <h3 className="eg-empty-title">No sessions</h3>
              <p className="eg-empty-desc">No examination sessions match the current filters.</p>
            </div>
          ) : (
            <>
              <div className="eg-table-wrap">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>Status</th>
                      <th>Gate</th>
                      <th>Session</th>
                      <th>Date</th>
                      <th>Details</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sessions.map((session) => (
                      <tr key={session.id}>
                        <td>
                          <span className={`eg-badge ${statusBadgeClass(session.status)}`}>
                            {session.status}
                          </span>
                        </td>
                        <td>
                          <span className={`eg-badge ${gateBadgeClass(session.gate_status)}`}>
                            {session.gate_status}
                          </span>
                        </td>
                        <td>
                          <Link
                            href={`/examination-sessions/${session.id}`}
                            className="eg-mono-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          >
                            Session #{session.id}
                          </Link>
                        </td>
                        <td>
                          <span className="eg-mono-sm text-[var(--text-muted)]">
                            {new Date(session.created_at).toLocaleString()}
                          </span>
                        </td>
                        <td>
                          <div className="flex items-center gap-3">
                            <span className="eg-mono-sm text-[var(--text-muted)]">
                              Exam #{session.exam_id} / Hall #{session.exam_hall_id}
                            </span>
                            {session.expected_capacity && (
                              <span className="eg-mono-sm text-[var(--text-muted)]">
                                Cap: {session.expected_capacity}
                              </span>
                            )}
                            {session.created_by && (
                              <span className="eg-mono-sm text-[var(--text-muted)]">
                                By: {session.created_by}
                              </span>
                            )}
                          </div>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          {session.status === "NOT_STARTED" && (
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => handleStart(session.id)}
                                disabled={actionLoading === session.id}
                                className="eg-btn eg-btn-primary text-xs"
                              >
                                Start
                              </button>
                              <button
                                onClick={() => handleCancel(session.id)}
                                disabled={actionLoading === session.id}
                                className="eg-btn text-xs"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                          {session.status === "IN_PROGRESS" && (
                            <div className="flex justify-end gap-2">
                              <button
                                onClick={() => handleEnd(session.id)}
                                disabled={actionLoading === session.id}
                                className="eg-btn eg-btn-primary text-xs"
                              >
                                End
                              </button>
                              <button
                                onClick={() => handleCancel(session.id)}
                                disabled={actionLoading === session.id}
                                className="eg-btn text-xs"
                              >
                                Cancel
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {totalPages > 1 && (
                <div className="eg-pagination">
                  <span className="eg-pagination-info">
                    Page {page} of {totalPages} &middot; {total} sessions
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className="eg-btn disabled:opacity-30"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className="eg-btn disabled:opacity-30"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AppShell>
  );
}
