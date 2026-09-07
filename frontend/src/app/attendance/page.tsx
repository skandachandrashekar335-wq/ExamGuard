"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  getAttendanceSummary,
  type AttendanceSummaryResponse,
} from "@/lib/attendance-api";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";

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
      const data = await apiRequest<ExamListResponse>(
        `/api/v1/exams${qs({ page, page_size: pageSize })}`
      );
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
    <AppShell>
      <div className="bg-[var(--bg-base)]">
        <div className="eg-page">
          <div className="eg-page-header">
            <Link href="/dashboard" className="eg-breadcrumb">
              &larr; Dashboard
            </Link>
            <h1 className="eg-page-title">Attendance</h1>
            <p className="eg-page-desc">
              Exam attendance tracking — select an exam to view records
            </p>
          </div>

          {error && (
            <div className="glass-surface border border-[var(--border)] p-4 mb-6">
              <span className="eg-body text-[var(--text-secondary)]">{error}</span>
            </div>
          )}

          {loading ? (
            <div className="glass-surface p-12 text-center">
              <span className="eg-body text-[var(--text-muted)]">
                Loading exams...
              </span>
            </div>
          ) : exams.length === 0 ? (
            <div className="eg-empty">
              <h3 className="eg-empty-title">No exams</h3>
              <p className="eg-empty-desc">No exams have been created yet.</p>
            </div>
          ) : (
            <>
              <div className="eg-table-wrap">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Exam</th>
                      <th>Date</th>
                      <th>Time</th>
                      <th>Registered</th>
                      <th>Present</th>
                      <th>Rate</th>
                      <th style={{ textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exams.map((exam) => {
                      const s = summaries[exam.id];
                      return (
                        <tr key={exam.id}>
                          <td className="font-mono text-sm">{exam.id}</td>
                          <td>{exam.exam_name}</td>
                          <td>{exam.exam_date}</td>
                          <td>
                            {exam.start_time} — {exam.end_time}
                          </td>
                          <td>{s ? s.total_registered : "—"}</td>
                          <td>{s ? s.total_present : "—"}</td>
                          <td>
                            {s ? `${Math.round(s.attendance_rate)}%` : "—"}
                          </td>
                          <td style={{ textAlign: "right" }}>
                            <Link
                              href={`/attendance/${exam.id}`}
                              className="eg-mono-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
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

              {totalPages > 1 && (
                <div className="eg-pagination">
                  <span className="eg-pagination-info">
                    Page {page} of {totalPages} &middot; {total} exams
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage(Math.max(1, page - 1))}
                      disabled={page === 1}
                      className="eg-btn disabled:opacity-30"
                    >
                      Previous
                    </button>
                    <button
                      onClick={() => setPage(Math.min(totalPages, page + 1))}
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
