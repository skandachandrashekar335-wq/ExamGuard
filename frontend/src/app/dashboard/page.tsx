"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

interface ExamListItem {
  id: number;
  subject_id: number;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
  is_active: boolean;
  subject_code: string | null;
  subject_name: string | null;
}

interface StudentRow {
  student_id: number;
  student_usn: string;
  student_name: string;
  registration_id: number;
  registration_status: string;
  seat_assignment_id: number | null;
  seat_number: string | null;
  hall_name: string | null;
  verification_status: string;
  document_id: number | null;
  extraction_check: string | null;
  match_check: string | null;
  review_check: string | null;
  decision: string | null;
  ocr_avg_confidence: number | null;
  match_status: string | null;
  verification_created_at: string | null;
}

interface DashboardSummary {
  exam_id: number;
  exam_name: string;
  exam_date: string;
  total_registered: number;
  total_verified: number;
  total_failed: number;
  total_review_required: number;
  total_incomplete: number;
  total_not_uploaded: number;
  total_seated: number;
  verification_rate: number;
}

interface DashboardData {
  summary: DashboardSummary;
  students: StudentRow[];
}

interface BatchResult {
  total: number;
  processed: number;
  matched: number;
  verified: number;
  failed: number;
  results: {
    document_id: number;
    step: string;
    status: string;
    error?: string;
    decision?: string;
  }[];
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATUS_STYLES: Record<string, string> = {
  VERIFIED: "bg-emerald-500/20 text-emerald-400",
  FAILED: "bg-pink-500/20 text-pink-400",
  REVIEW_REQUIRED: "bg-amber-500/20 text-amber-400",
  INCOMPLETE: "bg-cyan-500/20 text-cyan-400",
  NOT_UPLOADED: "bg-[#222] text-[#666]",
};

const STATUS_LABELS: Record<string, string> = {
  VERIFIED: "Verified",
  FAILED: "Failed",
  REVIEW_REQUIRED: "Review Required",
  INCOMPLETE: "Incomplete",
  NOT_UPLOADED: "Not Uploaded",
};

export default function DashboardPage() {
  const [exams, setExams] = useState<ExamListItem[]>([]);
  const [selectedExamId, setSelectedExamId] = useState<number | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [batchVerifying, setBatchVerifying] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [selectedDocs, setSelectedDocs] = useState<Set<number>>(new Set());

  const fetchDashboard = useCallback(() => {
    if (!selectedExamId) {
      setDashboard(null);
      return;
    }
    setLoading(true);
    setError("");
    fetch(`${API}/api/v1/exams/${selectedExamId}/dashboard`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load dashboard");
        return r.json();
      })
      .then((data: DashboardData) => {
        setDashboard(data);
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [selectedExamId]);

  useEffect(() => {
    fetch(`${API}/api/v1/exams?page=1&page_size=100`)
      .then((r) => r.json())
      .then((data) => setExams(data.items || []))
      .catch(() => setError("Failed to load exams"));
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const filteredStudents =
    dashboard?.students.filter(
      (s) =>
        !search ||
        s.student_usn.toLowerCase().includes(search.toLowerCase()) ||
        s.student_name.toLowerCase().includes(search.toLowerCase())
    ) || [];

  const handleSelectDoc = (docId: number) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) {
        next.delete(docId);
      } else {
        next.add(docId);
      }
      return next;
    });
  };

  const handleSelectAll = () => {
    const docIds = filteredStudents
      .filter((s) => s.document_id !== null)
      .map((s) => s.document_id!);
    setSelectedDocs((prev) => {
      if (prev.size === docIds.length) {
        return new Set();
      }
      return new Set(docIds);
    });
  };

  const handleBatchVerify = async () => {
    if (selectedDocs.size === 0) return;
    setBatchVerifying(true);
    setError("");
    setBatchResult(null);

    try {
      const res = await fetch(`${API}/api/v1/documents/batch-verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ document_ids: Array.from(selectedDocs) }),
      });

      if (!res.ok) throw new Error("Batch verification failed");
      const data: BatchResult = await res.json();
      setBatchResult(data);
      setSelectedDocs(new Set());
      fetchDashboard();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBatchVerifying(false);
    }
  };

  const summary = dashboard?.summary;

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Verification Dashboard
        </h1>
        <p className="text-[#999] mb-8">
          Exam-level verification status overview
        </p>

        <div className="flex gap-4 mb-8 items-center">
          <Link
            href="/monitoring"
            className="text-xs font-mono uppercase tracking-wider text-[#666] hover:text-white transition-colors"
          >
            Monitoring &rarr;
          </Link>
        </div>

        <div className="flex gap-4 mb-8">
          <select
            value={selectedExamId ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedExamId(val ? Number(val) : null);
              setSelectedDocs(new Set());
              setBatchResult(null);
            }}
            className="flex-1 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">Select an exam...</option>
            {exams.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.exam_name} — {ex.exam_date} ({ex.subject_code || "N/A"})
              </option>
            ))}
          </select>
        </div>

        {error && (
          <p className="text-pink-400 text-sm mb-6">{error}</p>
        )}

        {loading && (
          <p className="text-[#666] text-sm mb-6">Loading dashboard...</p>
        )}

        {batchResult && (
          <div className="bg-[#111] border border-emerald-500/30 rounded-lg p-4 mb-6">
            <h3 className="text-sm font-semibold text-emerald-400 mb-2">
              Batch Verification Complete
            </h3>
            <div className="grid grid-cols-5 gap-4 text-sm">
              <div>
                <span className="text-[#666]">Total:</span>{" "}
                {batchResult.total}
              </div>
              <div>
                <span className="text-[#666]">Processed:</span>{" "}
                {batchResult.processed}
              </div>
              <div>
                <span className="text-[#666]">Matched:</span>{" "}
                {batchResult.matched}
              </div>
              <div>
                <span className="text-emerald-400">Verified:</span>{" "}
                {batchResult.verified}
              </div>
              <div>
                <span className="text-pink-400">Failed:</span>{" "}
                {batchResult.failed}
              </div>
            </div>
          </div>
        )}

        {summary && (
          <>
            <div className="mb-4">
              <h2 className="text-xl font-semibold">
                {summary.exam_name}
              </h2>
              <p className="text-[#999] text-sm">
                {summary.exam_date} &middot; {summary.total_registered} registered
              </p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <StatCard
                label="Registered"
                value={summary.total_registered}
                color="cyan"
              />
              <StatCard
                label="Verified"
                value={summary.total_verified}
                color="emerald"
                rate={summary.verification_rate}
              />
              <StatCard
                label="Failed"
                value={summary.total_failed}
                color="pink"
              />
              <StatCard
                label="Review Required"
                value={summary.total_review_required}
                color="amber"
              />
              <StatCard
                label="Incomplete"
                value={summary.total_incomplete}
                color="cyan"
              />
              <StatCard
                label="Not Uploaded"
                value={summary.total_not_uploaded}
                color="neutral"
              />
              <StatCard
                label="Seated"
                value={summary.total_seated}
                color="violet"
              />
              <StatCard
                label="Verification Rate"
                value={`${summary.verification_rate}%`}
                color="emerald"
              />
            </div>

            <div className="flex gap-4 mb-4">
              <input
                type="text"
                placeholder="Filter by USN or name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
              />
              <button
                onClick={handleSelectAll}
                className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5"
              >
                {selectedDocs.size ===
                filteredStudents.filter((s) => s.document_id).length
                  ? "Deselect All"
                  : "Select All"}
              </button>
              <button
                onClick={handleBatchVerify}
                disabled={selectedDocs.size === 0 || batchVerifying}
                className="bg-gradient-to-r from-cyan-500 to-emerald-500 px-4 py-2 rounded-lg font-medium text-sm hover:opacity-90 disabled:opacity-30"
              >
                {batchVerifying
                  ? "Verifying..."
                  : `Batch Verify (${selectedDocs.size})`}
              </button>
            </div>

            <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                    <th className="px-6 py-3 w-10"></th>
                    <th className="px-6 py-3">USN</th>
                    <th className="px-6 py-3">Name</th>
                    <th className="px-6 py-3">Seat</th>
                    <th className="px-6 py-3">Hall</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Decision</th>
                    <th className="px-6 py-3">OCR Conf</th>
                    <th className="px-6 py-3">Match</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((s) => (
                    <tr
                      key={s.student_id}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-6 py-3">
                        {s.document_id && (
                          <input
                            type="checkbox"
                            checked={selectedDocs.has(s.document_id)}
                            onChange={() => handleSelectDoc(s.document_id!)}
                            className="accent-cyan-500"
                          />
                        )}
                      </td>
                      <td className="px-6 py-3 font-mono text-sm">
                        {s.student_usn}
                      </td>
                      <td className="px-6 py-3 text-sm">{s.student_name}</td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {s.seat_number || "—"}
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {s.hall_name || "—"}
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            STATUS_STYLES[s.verification_status] ||
                            "bg-[#222] text-[#666]"
                          }`}
                        >
                          {STATUS_LABELS[s.verification_status] ||
                            s.verification_status}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {s.decision
                          ? s.decision.replace(/_/g, " ")
                          : "—"}
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {s.ocr_avg_confidence != null
                          ? `${s.ocr_avg_confidence.toFixed(1)}%`
                          : "—"}
                      </td>
                      <td className="px-6 py-3 text-sm text-[#999]">
                        {s.match_status
                          ? s.match_status.replace(/_/g, " ")
                          : "—"}
                      </td>
                    </tr>
                  ))}
                  {filteredStudents.length === 0 && (
                    <tr>
                      <td
                        colSpan={9}
                        className="px-6 py-8 text-center text-[#666]"
                      >
                        {search
                          ? "No students match the filter"
                          : "No students registered for this exam"}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!dashboard && !loading && !error && (
          <div className="text-center py-20 text-[#666]">
            Select an exam to view its verification dashboard
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  color,
  rate,
}: {
  label: string;
  value: number | string;
  color: string;
  rate?: number;
}) {
  const colorMap: Record<string, string> = {
    cyan: "border-cyan-500/30",
    emerald: "border-emerald-500/30",
    pink: "border-pink-500/30",
    amber: "border-amber-500/30",
    violet: "border-violet-500/30",
    neutral: "border-white/10",
  };

  return (
    <div
      className={`bg-[#111] border ${
        colorMap[color] || "border-white/10"
      } rounded-lg p-4`}
    >
      <div className="text-xs text-[#666] mb-1">{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {rate !== undefined && (
        <div className="text-xs text-emerald-400 mt-1">{rate}% pass rate</div>
      )}
    </div>
  );
}
