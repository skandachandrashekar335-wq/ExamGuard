"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  listEntryEvents,
  type AttendanceEvent,
} from "@/lib/attendance-api";

const EVENT_TYPE_CLASSES: Record<string, string> = {
  AUTO_RECORDED: "border-white/30 text-white",
  MANUAL_CORRECTION: "border-white/20 text-[var(--text-secondary)]",
  MANUAL_ABSENT: "border-white/20 text-[var(--text-secondary)]",
  ENTRY_GRANTED: "border-white/40 text-white",
  ENTRY_DENIED: "border-white/10 text-[var(--text-muted)]",
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
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <div className="mb-6">
          <Link
            href="/attendance"
            className="eg-mono-sm text-[var(--text-muted)] hover:text-white transition-colors"
          >
            ← Attendance
          </Link>
        </div>

        <h1 className="eg-display text-3xl mb-2">Event History</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Entry verification #{entryVerificationId}
        </p>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-red-400">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading events...
            </span>
          </div>
        ) : events.length === 0 ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-2">
              No events
            </h3>
            <p className="text-sm text-[var(--text-muted)]">
              No attendance events found for this entry verification.
            </p>
          </div>
        ) : (
          <div className="border border-white/10 bg-[var(--bg-raised)] overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Status Snapshot
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Student
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Exam
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Recorded By
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Reason
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr
                    key={ev.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-sm">{ev.id}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          EVENT_TYPE_CLASSES[ev.event_type] ||
                          "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {ev.event_type}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[10px] eg-mono border border-white/10 px-2 py-0.5 text-[var(--text-secondary)]">
                        {ev.status_snapshot}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{ev.student_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{ev.exam_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      {ev.recorded_by ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)] max-w-[200px] truncate">
                      {ev.reason ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                      {new Date(ev.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
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
    </div>
  );
}
