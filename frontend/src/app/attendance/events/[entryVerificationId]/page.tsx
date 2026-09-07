"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  listEntryEvents,
  type AttendanceEvent,
} from "@/lib/attendance-api";
import AppShell from "@/components/AppShell";

const EVENT_TYPE_BADGE: Record<string, string> = {
  AUTO_RECORDED: "eg-badge-success",
  MANUAL_CORRECTION: "eg-badge-warning",
  MANUAL_ABSENT: "eg-badge-warning",
  ENTRY_GRANTED: "eg-badge-success",
  ENTRY_DENIED: "eg-badge-danger",
};

export default function AttendanceEventsPage() {
  const params = useParams();
  const entryVerificationId = Number(params.entryVerificationId);

  const [events, setEvents] = useState<AttendanceEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchEvents = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listEntryEvents(entryVerificationId, {
        page,
        page_size: pageSize,
      });
      setEvents(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load attendance events");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [entryVerificationId, page]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/attendance" className="eg-breadcrumb">
            ← Attendance
          </Link>
          <h1 className="eg-page-title">Event History</h1>
          <p className="eg-page-desc">
            Entry verification #{entryVerificationId}
          </p>
        </div>

        {error && (
          <div className="glass-surface p-4 mb-6">
            <span className="eg-mono text-sm" style={{ color: "var(--danger)" }}>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="glass-surface p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading events...
            </span>
          </div>
        ) : events.length === 0 ? (
          <div className="eg-empty">
            <div className="eg-empty-title">No events</div>
            <div className="eg-empty-desc">
              No attendance events found for this entry verification.
            </div>
          </div>
        ) : (
          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Status Snapshot</th>
                  <th>Student</th>
                  <th>Exam</th>
                  <th>Recorded By</th>
                  <th>Reason</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>{ev.id}</td>
                    <td>
                      <span className={`eg-badge ${EVENT_TYPE_BADGE[ev.event_type] || "eg-badge-neutral"}`}>
                        {ev.event_type}
                      </span>
                    </td>
                    <td>
                      <span className="eg-badge eg-badge-info">
                        {ev.status_snapshot}
                      </span>
                    </td>
                    <td style={{ color: "var(--text-secondary)" }}>#{ev.student_id}</td>
                    <td style={{ color: "var(--text-secondary)" }}>#{ev.exam_id}</td>
                    <td style={{ color: "var(--text-secondary)" }}>
                      {ev.recorded_by ?? "—"}
                    </td>
                    <td
                      className="max-w-[200px] truncate"
                      style={{ color: "var(--text-secondary)" }}
                    >
                      {ev.reason ?? "—"}
                    </td>
                    <td
                      style={{
                        color: "var(--text-muted)",
                        fontFamily: "var(--font-mono)",
                        fontSize: "0.75rem",
                      }}
                    >
                      {new Date(ev.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="eg-pagination mt-4">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Prev
            </button>
            <span className="eg-mono-sm text-[var(--text-muted)]">
              {page} / {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
