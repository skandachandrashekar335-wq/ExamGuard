"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";

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

import { apiRequest, qs } from "@/lib/api";

const STATUS_BADGE: Record<string, string> = {
  VERIFIED: "eg-badge-success",
  FAILED: "eg-badge-danger",
  REVIEW_REQUIRED: "eg-badge-warning",
  INCOMPLETE: "eg-badge-info",
  NOT_UPLOADED: "eg-badge-neutral",
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
    if (!selectedExamId) { setDashboard(null); return; }
    setLoading(true);
    setError("");
    apiRequest<DashboardData>(`/api/v1/exams/${selectedExamId}/dashboard`)
      .then((data) => { setDashboard(data); setLoading(false); })
      .catch((e) => { setError(e.message); setLoading(false); });
  }, [selectedExamId]);

  useEffect(() => {
    apiRequest<{ items: ExamListItem[] }>("/api/v1/exams?page=1&page_size=100")
      .then((data) => setExams(data.items || []))
      .catch(() => setError("Failed to load exams"));
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const filteredStudents =
    dashboard?.students.filter(
      (s) => !search || s.student_usn.toLowerCase().includes(search.toLowerCase()) || s.student_name.toLowerCase().includes(search.toLowerCase())
    ) || [];

  const handleSelectDoc = (docId: number) => {
    setSelectedDocs((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId); else next.add(docId);
      return next;
    });
  };

  const handleSelectAll = () => {
    const docIds = filteredStudents.filter((s) => s.document_id !== null).map((s) => s.document_id!);
    setSelectedDocs((prev) => prev.size === docIds.length ? new Set() : new Set(docIds));
  };

  const handleBatchVerify = async () => {
    if (selectedDocs.size === 0) return;
    setBatchVerifying(true);
    setError("");
    setBatchResult(null);
    try {
      const data = await apiRequest<BatchResult>("/api/v1/documents/batch-verify", {
        method: "POST",
        body: JSON.stringify({ document_ids: Array.from(selectedDocs) }),
      });
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
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">← HOME</Link>
          <h1 className="eg-page-title">Verification Dashboard</h1>
          <p className="eg-page-desc">Exam-level verification status overview</p>
        </div>

        <div className="eg-filter-bar">
          <Link href="/monitoring" className="eg-btn text-xs">Monitoring →</Link>
          <Link href="/examination-sessions" className="eg-btn text-xs">Sessions →</Link>
          <Link href="/security-events" className="eg-btn text-xs">Security Events →</Link>
          <Link href="/security-alerts" className="eg-btn text-xs">Security Alerts →</Link>
        </div>

        <div className="mb-6">
          <select
            value={selectedExamId ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              setSelectedExamId(val ? Number(val) : null);
              setSelectedDocs(new Set());
              setBatchResult(null);
            }}
            className="eg-select w-full max-w-lg"
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
          <div className="eg-card-flat mb-6" style={{ borderColor: "var(--danger)" }}>
            <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>
          </div>
        )}

        {loading && (
          <div className="eg-card-flat p-8 text-center mb-6">
            <p className="text-sm text-[var(--text-muted)]">Loading dashboard...</p>
          </div>
        )}

        {batchResult && (
          <div className="eg-card mb-6" style={{ borderColor: "rgba(45,159,111,0.3)" }}>
            <p className="text-sm font-medium mb-3" style={{ color: "var(--success)" }}>Batch Verification Complete</p>
            <div className="grid grid-cols-5 gap-4 text-sm">
              <div><span className="text-[var(--text-muted)]">Total: </span>{batchResult.total}</div>
              <div><span className="text-[var(--text-muted)]">Processed: </span>{batchResult.processed}</div>
              <div><span className="text-[var(--text-muted)]">Matched: </span>{batchResult.matched}</div>
              <div style={{ color: "var(--success)" }}>Verified: {batchResult.verified}</div>
              <div style={{ color: "var(--danger)" }}>Failed: {batchResult.failed}</div>
            </div>
          </div>
        )}

        {summary && (
          <>
            <div className="mb-6">
              <h2 className="text-xl" style={{ fontFamily: "var(--font-display)", color: "var(--text-primary)" }}>{summary.exam_name}</h2>
              <p className="text-sm text-[var(--text-muted)]">{summary.exam_date} · {summary.total_registered} registered</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
              <div className="eg-metric">
                <div className="eg-metric-label">Registered</div>
                <div className="eg-metric-value">{summary.total_registered}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Verified</div>
                <div className="eg-metric-value">{summary.total_verified}</div>
                <div className="eg-metric-detail" style={{ color: "var(--success)" }}>{summary.verification_rate}% rate</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Failed</div>
                <div className="eg-metric-value">{summary.total_failed}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Review Required</div>
                <div className="eg-metric-value">{summary.total_review_required}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Incomplete</div>
                <div className="eg-metric-value">{summary.total_incomplete}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Not Uploaded</div>
                <div className="eg-metric-value">{summary.total_not_uploaded}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Seated</div>
                <div className="eg-metric-value">{summary.total_seated}</div>
              </div>
              <div className="eg-metric">
                <div className="eg-metric-label">Verification Rate</div>
                <div className="eg-metric-value">{summary.verification_rate}%</div>
              </div>
            </div>

            <div className="eg-filter-bar">
              <input
                type="text"
                placeholder="Filter by USN or name..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="eg-input flex-1 max-w-sm"
              />
              <button onClick={handleSelectAll} className="eg-btn text-xs">
                {selectedDocs.size === filteredStudents.filter((s) => s.document_id).length ? "Deselect All" : "Select All"}
              </button>
              <button
                onClick={handleBatchVerify}
                disabled={selectedDocs.size === 0 || batchVerifying}
                className="eg-btn eg-btn-primary text-xs"
              >
                {batchVerifying ? "Verifying..." : `Batch Verify (${selectedDocs.size})`}
              </button>
            </div>

            <div className="eg-table-wrap">
              <table className="eg-table">
                <thead>
                  <tr>
                    <th className="w-10"></th>
                    <th>USN</th>
                    <th>Name</th>
                    <th>Seat</th>
                    <th>Hall</th>
                    <th>Status</th>
                    <th>Decision</th>
                    <th>OCR Conf</th>
                    <th>Match</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((s) => (
                    <tr key={s.student_id}>
                      <td>
                        {s.document_id && (
                          <input
                            type="checkbox"
                            checked={selectedDocs.has(s.document_id)}
                            onChange={() => handleSelectDoc(s.document_id!)}
                            className="eg-checkbox"
                          />
                        )}
                      </td>
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8125rem" }}>{s.student_usn}</td>
                      <td>{s.student_name}</td>
                      <td style={{ color: "var(--text-muted)" }}>{s.seat_number || "—"}</td>
                      <td style={{ color: "var(--text-muted)" }}>{s.hall_name || "—"}</td>
                      <td>
                        <span className={`eg-badge ${STATUS_BADGE[s.verification_status] || "eg-badge-neutral"}`}>
                          {STATUS_LABELS[s.verification_status] || s.verification_status}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>{s.decision ? s.decision.replace(/_/g, " ") : "—"}</td>
                      <td style={{ color: "var(--text-muted)" }}>{s.ocr_avg_confidence != null ? `${s.ocr_avg_confidence.toFixed(1)}%` : "—"}</td>
                      <td style={{ color: "var(--text-muted)" }}>{s.match_status ? s.match_status.replace(/_/g, " ") : "—"}</td>
                    </tr>
                  ))}
                  {filteredStudents.length === 0 && (
                    <tr>
                      <td colSpan={9} className="text-center" style={{ padding: "2rem", color: "var(--text-muted)" }}>
                        {search ? "No students match the filter" : "No students registered for this exam"}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {!dashboard && !loading && !error && (
          <div className="eg-empty">
            <div className="eg-empty-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="18" height="18" rx="3" stroke="var(--text-muted)" strokeWidth="1.5"/><path d="M3 9h18M9 3v18" stroke="var(--text-muted)" strokeWidth="1.5"/></svg>
            </div>
            <p className="eg-empty-title">Select an Exam</p>
            <p className="eg-empty-desc">Choose an examination from the dropdown above to view its verification dashboard.</p>
          </div>
        )}
      </div>
    </AppShell>
  );
}
