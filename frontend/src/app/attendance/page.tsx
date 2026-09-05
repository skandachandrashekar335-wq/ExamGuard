"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getAttendanceSummary,
  type AttendanceSummaryResponse,
} from "@/lib/attendance-api";

interface Exam {
  id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
  is_active: boolean;
}

interface ExamListResponse {
  items: Exam[];
  total: number;
  page: number;
  page_size: number;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function AttendancePage() {
  const [exams, setExams] = useState<Exam[]>([]);
  const [summaries, setSummaries] = useState<
    Record<number, AttendanceSummaryResponse>
  >({});
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchExams = async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      const res = await fetch(`${API}/api/v1/exams?${params}`);
      const data: ExamListResponse = await res.json();
      setExams(data.items);
      setTotal(data.total);

      const summMap: Record<number, AttendanceSummaryResponse> = {};
      await Promise.all(
        data.items.map(async (exam) => {
          try {
            summMap[exam.id] = await getAttendanceSummary(exam.id);
          } catch {
            // summary unavailable for this exam
          }
        }),
      );
      setSummaries(summMap);
    } catch {
      setError("Failed to load exams");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExams();
  }, [page]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="eg-display text-3xl mb-2">Attendance</h1>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Exam attendance tracking — select an exam to view records
        </p>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-red-400">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading exams...
            </span>
          </div>
        ) : exams.length === 0 ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-2">
              No exams
            </h3>
            <p className="text-sm text-[var(--text-muted)]">
              No exams have been created yet.
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
                    Exam
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Date
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Time
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Registered
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Present
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Rate
                  </th>
                  <th className="px-4 py-3 text-right eg-mono-sm text-[var(--text-muted)]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {exams.map((exam) => {
                  const s = summaries[exam.id];
                  return (
                    <tr
                      key={exam.id}
                      className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-sm">{exam.id}</td>
                      <td className="px-4 py-3 text-sm">{exam.exam_name}</td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {exam.exam_date}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {exam.start_time} — {exam.end_time}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {s ? s.total_registered : "—"}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {s ? s.total_present : "—"}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                        {s ? `${Math.round(s.attendance_rate * 100)}%` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Link
                          href={`/attendance/${exam.id}`}
                          className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  );
                })}
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
