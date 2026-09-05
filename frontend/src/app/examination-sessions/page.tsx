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

const STATUSES = ["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "CANCELLED"];

function statusClass(s: string): string {
  if (s === "IN_PROGRESS") return "text-white font-bold";
  if (s === "NOT_STARTED") return "text-[var(--gray-300)]";
  if (s === "COMPLETED") return "text-[var(--text-muted)]";
  return "text-[var(--text-muted)]";
}

function gateClass(s: string): string {
  if (s === "GATES_OPEN") return "border border-white/20 px-2 py-0.5";
  return "border border-white/[0.06] px-2 py-0.5 text-[var(--text-muted)]";
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
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <Link
          href="/dashboard"
          className="eg-mono-sm text-[var(--text-muted)] hover:text-[var(--text-secondary)] mb-8 inline-block"
        >
          &larr; DASHBOARD
        </Link>

        <h1 className="eg-display text-3xl mb-2">EXAMINATION SESSIONS</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Manage session lifecycle, gate operations, and active hall monitoring.
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
          </div>
        </div>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-[var(--text-muted)]">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">Loading sessions...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="border border-white/[0.06] bg-[var(--bg-surface)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-1">NO SESSIONS</h3>
            <p className="text-sm text-[var(--text-muted)]">No examination sessions match the current filters.</p>
          </div>
        ) : (
          <>
            <div className="border border-white/[0.06] bg-[var(--bg-surface)]">
              <div className="px-4 py-3 border-b border-white/[0.06]">
                <span className="eg-mono-sm text-[var(--text-muted)]">
                  {total} SESSIONS
                </span>
              </div>
              <div className="divide-y divide-white/[0.04]">
                {sessions.map((session) => (
                  <div key={session.id} className="px-4 py-3">
                    <div className="flex items-start gap-4">
                      <span className={`eg-mono-sm shrink-0 w-28 ${statusClass(session.status)}`}>
                        {session.status}
                      </span>
                      <span className={`eg-mono-sm shrink-0 ${gateClass(session.gate_status)}`}>
                        {session.gate_status}
                      </span>
                      <Link
                        href={`/examination-sessions/${session.id}`}
                        className="eg-mono-sm flex-1 text-[var(--text-secondary)] hover:text-white"
                      >
                        SESSION #{session.id} — EXAM #{session.exam_id} / HALL #{session.exam_hall_id}
                      </Link>
                      <span className="eg-mono-sm shrink-0 text-[var(--text-muted)]">
                        {new Date(session.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center gap-3 text-xs">
                      {session.expected_capacity && (
                        <span className="eg-mono-sm text-[var(--text-muted)]">
                          CAPACITY: {session.expected_capacity}
                        </span>
                      )}
                      {session.created_by && (
                        <span className="eg-mono-sm text-[var(--text-muted)]">
                          BY: {session.created_by}
                        </span>
                      )}
                      {session.status === "NOT_STARTED" && (
                        <div className="flex gap-2 ml-auto">
                          <button
                            onClick={() => handleStart(session.id)}
                            disabled={actionLoading === session.id}
                            className="eg-btn text-xs"
                          >
                            START
                          </button>
                          <button
                            onClick={() => handleCancel(session.id)}
                            disabled={actionLoading === session.id}
                            className="eg-btn text-xs"
                          >
                            CANCEL
                          </button>
                        </div>
                      )}
                      {session.status === "IN_PROGRESS" && (
                        <div className="flex gap-2 ml-auto">
                          <button
                            onClick={() => handleEnd(session.id)}
                            disabled={actionLoading === session.id}
                            className="eg-btn text-xs"
                          >
                            END
                          </button>
                          <button
                            onClick={() => handleCancel(session.id)}
                            disabled={actionLoading === session.id}
                            className="eg-btn text-xs"
                          >
                            CANCEL
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
