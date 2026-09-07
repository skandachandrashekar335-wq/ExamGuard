"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";

interface Document {
  id: number;
  original_filename: string;
  stored_key: string;
  content_type: string;
  file_size: number;
  document_type: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface ExtractedField {
  id: number;
  field_name: string;
  extracted_value: string | null;
  corrected_value: string | null;
  ocr_confidence: number | null;
  pattern_match: boolean | null;
  label_found: boolean | null;
  database_match: boolean | null;
  extraction_method: string | null;
  validation_status: string;
  review_status: string;
}

interface ExtractionResult {
  id: number;
  document_id: number;
  ocr_engine: string;
  ocr_avg_confidence: number;
  processing_time_ms: number | null;
  status: string;
  created_at: string;
  fields: ExtractedField[];
}

interface ProcessResponse {
  extraction_result_id: number;
  status: string;
  ocr_engine: string;
  ocr_avg_confidence: number;
  processing_time_ms: number | null;
  fields_count: number;
  review_required: boolean;
}

interface MatchSignal {
  id: number;
  match_result_id: number;
  field_name: string;
  extracted_value: string | null;
  expected_value: string | null;
  matched: boolean;
  signal_type: string;
  details: string | null;
  created_at: string;
}

interface MatchResult {
  id: number;
  document_id: number;
  extraction_result_id: number;
  student_id: number | null;
  exam_id: number | null;
  registration_id: number | null;
  seat_assignment_id: number | null;
  overall_status: string;
  created_at: string;
  updated_at: string;
  signals: MatchSignal[];
}

interface ReviewField {
  id: number;
  field_name: string;
  extracted_value: string | null;
  corrected_value: string | null;
  ocr_confidence: number | null;
  review_status: string;
  extraction_method: string | null;
  label_found: boolean | null;
  pattern_match: boolean | null;
}

interface ReviewProgress {
  total_fields: number;
  reviewed_count: number;
  review_required_count: number;
}

interface ReviewData {
  extraction_result_id: number;
  document_id: number;
  ocr_engine: string;
  ocr_avg_confidence: number;
  processing_time_ms: number | null;
  extraction_status: string;
  reviewed_by: number | null;
  reviewed_at: string | null;
  progress: ReviewProgress;
  fields: ReviewField[];
}

interface VerificationOutcome {
  id: number;
  document_id: number;
  extraction_result_id: number | null;
  match_result_id: number | null;
  student_id: number | null;
  exam_id: number | null;
  decision: string;
  extraction_check: string;
  match_check: string;
  review_check: string;
  ocr_avg_confidence: number | null;
  match_status: string | null;
  review_completed: boolean;
  reasoning: string | null;
  created_at: string;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("HALL_TICKET");
  const [processingId, setProcessingId] = useState<number | null>(null);
  const [extractionResult, setExtractionResult] = useState<ExtractionResult | null>(null);
  const [showExtraction, setShowExtraction] = useState(false);
  const [matchingId, setMatchingId] = useState<number | null>(null);
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const [showMatch, setShowMatch] = useState(false);
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [showReview, setShowReview] = useState(false);
  const [reviewingId, setReviewingId] = useState<number | null>(null);
  const [editingFieldId, setEditingFieldId] = useState<number | null>(null);
  const [editValue, setEditValue] = useState("");
  const [completingReview, setCompletingReview] = useState(false);
  const [verifyingId, setVerifyingId] = useState<number | null>(null);
  const [verificationOutcome, setVerificationOutcome] = useState<VerificationOutcome | null>(null);
  const [showVerification, setShowVerification] = useState(false);

  const fetchDocuments = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: "10",
    });
    const res = await fetch(`${API}/api/v1/documents?${params}`);
    const data = await res.json();
    setDocuments(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchDocuments();
  }, [page]);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setMessage("");
    setError("");

    const formData = new FormData();
    formData.append("file", selectedFile);

    const res = await fetch(
      `${API}/api/v1/documents?document_type=${docType}`,
      { method: "POST", body: formData }
    );

    if (res.ok) {
      setMessage("Document uploaded successfully");
      setSelectedFile(null);
      fetchDocuments();
    } else {
      const err = await res.json();
      setError(err.detail || "Upload failed");
    }
    setUploading(false);
  };

  const handleProcess = async (docId: number) => {
    setProcessingId(docId);
    setMessage("");
    setError("");

    const res = await fetch(`${API}/api/v1/documents/${docId}/process`, {
      method: "POST",
    });

    if (res.ok) {
      const result: ProcessResponse = await res.json();
      setMessage(`Document processed: ${result.fields_count} fields extracted`);
      fetchDocuments();
    } else {
      const err = await res.json();
      setError(err.detail || "Processing failed");
    }
    setProcessingId(null);
  };

  const handleViewExtraction = async (docId: number) => {
    setMessage("");
    setError("");

    const res = await fetch(`${API}/api/v1/documents/${docId}/extraction`);

    if (res.ok) {
      const result: ExtractionResult = await res.json();
      setExtractionResult(result);
      setShowExtraction(true);
    } else {
      const err = await res.json();
      setError(err.detail || "No extraction results found");
    }
  };

  const handleStartReview = async (docId: number) => {
    setReviewingId(docId);
    setMessage("");
    setError("");

    const res = await fetch(`${API}/api/v1/documents/${docId}/review`);

    if (res.ok) {
      const data: ReviewData = await res.json();
      setReviewData(data);
      setShowReview(true);
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to load review data");
    }
    setReviewingId(null);
  };

  const handleCorrectField = async (fieldId: number) => {
    if (!reviewData || !editValue.trim()) return;

    const res = await fetch(
      `${API}/api/v1/documents/${reviewData.document_id}/review/fields/${fieldId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          corrected_value: editValue.trim(),
          review_status: "REVIEWED",
        }),
      }
    );

    if (res.ok) {
      const updated: ReviewField = await res.json();
      setReviewData((prev) => {
        if (!prev) return prev;
        const fields = prev.fields.map((f) => (f.id === fieldId ? updated : f));
        const reviewed_count = fields.filter(
          (f) => f.review_status === "REVIEWED"
        ).length;
        const review_required_count = fields.filter(
          (f) => f.review_status === "REVIEW_REQUIRED"
        ).length;
        return {
          ...prev,
          fields,
          progress: {
            ...prev.progress,
            reviewed_count,
            review_required_count,
          },
        };
      });
      setEditingFieldId(null);
      setEditValue("");
      setMessage("Field corrected");
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to correct field");
    }
  };

  const handleCompleteReview = async () => {
    if (!reviewData) return;
    setCompletingReview(true);
    setMessage("");
    setError("");

    const res = await fetch(
      `${API}/api/v1/documents/${reviewData.document_id}/review/complete`,
      { method: "POST" }
    );

    if (res.ok) {
      setMessage("Review completed successfully");
      setShowReview(false);
      setReviewData(null);
      fetchDocuments();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to complete review");
    }
    setCompletingReview(false);
  };

  const handleVerify = async (docId: number) => {
    setVerifyingId(docId);
    setMessage("");
    setError("");

    const res = await fetch(`${API}/api/v1/documents/${docId}/verification`, {
      method: "POST",
    });

    if (res.ok) {
      const outcome: VerificationOutcome = await res.json();
      setVerificationOutcome(outcome);
      setShowVerification(true);
      setMessage(`Verification: ${outcome.decision.replace("_", " ")}`);
    } else {
      const err = await res.json();
      setError(err.detail || "Verification failed");
    }
    setVerifyingId(null);
  };

  const handleMatch = async (docId: number) => {
    setMatchingId(docId);
    setMessage("");
    setError("");

    const res = await fetch(`${API}/api/v1/documents/${docId}/match`, {
      method: "POST",
    });

    if (res.ok) {
      const result: MatchResult = await res.json();
      setMatchResult(result);
      setShowMatch(true);
      setMessage(`Match completed: ${result.overall_status.replace("_", " ")}`);
    } else {
      const err = await res.json();
      setError(err.detail || "Matching failed");
    }
    setMatchingId(null);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const totalPages = Math.ceil(total / 10);

  if (showReview && reviewData) {
    const allReviewed = reviewData.progress.review_required_count === 0;
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <button
              onClick={() => {
                setShowReview(false);
                setReviewData(null);
                setEditingFieldId(null);
                setEditValue("");
              }}
              className="eg-btn mb-4"
            >
              ← Back to Documents
            </button>
            <h1 className="eg-page-title">Extraction Review</h1>
            <p className="eg-page-desc">
              Document #{reviewData.document_id} · {reviewData.ocr_engine} ·{" "}
              {reviewData.ocr_avg_confidence.toFixed(1)}% confidence
            </p>
          </div>

          <div className="glass-surface glass p-4 mb-6">
            <div className="flex items-center justify-between mb-2">
              <span style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>Review Progress</span>
              <span style={{ fontSize: "0.875rem" }}>
                {reviewData.progress.reviewed_count}/{reviewData.progress.total_fields} reviewed
              </span>
            </div>
            <div style={{ width: "100%", height: "8px", borderRadius: "4px", background: "var(--border)", overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  borderRadius: "4px",
                  background: "var(--accent)",
                  transition: "width 0.3s ease",
                  width: `${
                    reviewData.progress.total_fields > 0
                      ? (reviewData.progress.reviewed_count / reviewData.progress.total_fields) * 100
                      : 0
                  }%`,
                }}
              />
            </div>
          </div>

          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>OCR Value</th>
                  <th>Corrected</th>
                  <th>Confidence</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reviewData.fields.map((f) => (
                  <tr key={f.id}>
                    <td style={{ fontWeight: 500 }}>
                      {f.field_name.replace("_", " ")}
                    </td>
                    <td style={{ color: "var(--text-muted)" }}>
                      {f.extracted_value || "—"}
                    </td>
                    <td>
                      {editingFieldId === f.id ? (
                        <div className="flex gap-2 items-center">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            className="eg-input"
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === "Enter") handleCorrectField(f.id);
                              if (e.key === "Escape") {
                                setEditingFieldId(null);
                                setEditValue("");
                              }
                            }}
                          />
                          <button onClick={() => handleCorrectField(f.id)} className="eg-btn eg-btn-primary text-xs">
                            Save
                          </button>
                          <button
                            onClick={() => {
                              setEditingFieldId(null);
                              setEditValue("");
                            }}
                            className="eg-btn text-xs"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <span
                          style={{ color: f.corrected_value ? "var(--success, #22c55e)" : "var(--text-muted)" }}
                        >
                          {f.corrected_value || "—"}
                        </span>
                      )}
                    </td>
                    <td style={{ color: "var(--text-muted)" }}>
                      {f.ocr_confidence != null ? `${f.ocr_confidence.toFixed(1)}%` : "—"}
                    </td>
                    <td>
                      <span
                        className={`eg-badge ${
                          f.review_status === "REVIEWED"
                            ? "eg-badge-success"
                            : f.review_status === "AUTO_APPROVED"
                            ? "eg-badge-info"
                            : "eg-badge-warning"
                        }`}
                      >
                        {f.review_status.replace("_", " ")}
                      </span>
                    </td>
                    <td>
                      {editingFieldId !== f.id && (
                        <button
                          onClick={() => {
                            setEditingFieldId(f.id);
                            setEditValue(f.corrected_value || f.extracted_value || "");
                          }}
                          className="eg-btn text-xs"
                        >
                          Correct
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end mt-4">
            <button
              onClick={handleCompleteReview}
              disabled={!allReviewed || completingReview}
              className="eg-btn eg-btn-primary"
            >
              {completingReview ? "Completing..." : "Complete Review"}
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  if (showVerification && verificationOutcome) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <button
              onClick={() => {
                setShowVerification(false);
                setVerificationOutcome(null);
              }}
              className="eg-btn mb-4"
            >
              ← Back to Documents
            </button>
            <h1 className="eg-page-title">Verification Outcome</h1>
            <p className="eg-page-desc">
              Document #{verificationOutcome.document_id} ·{" "}
              <span
                className={`eg-badge ${
                  verificationOutcome.decision === "VERIFIED"
                    ? "eg-badge-success"
                    : verificationOutcome.decision === "FAILED"
                    ? "eg-badge-danger"
                    : verificationOutcome.decision === "REVIEW_REQUIRED"
                    ? "eg-badge-warning"
                    : "eg-badge-info"
                }`}
              >
                {verificationOutcome.decision.replace("_", " ")}
              </span>
            </p>
          </div>

          <div className="eg-grid-3 mb-8">
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Extraction Check</div>
              <span
                className={`eg-badge ${
                  verificationOutcome.extraction_check === "PASSED"
                    ? "eg-badge-success"
                    : verificationOutcome.extraction_check === "FAILED"
                    ? "eg-badge-danger"
                    : "eg-badge-warning"
                }`}
              >
                {verificationOutcome.extraction_check.replace("_", " ")}
              </span>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Match Check</div>
              <span
                className={`eg-badge ${
                  verificationOutcome.match_check === "PASSED"
                    ? "eg-badge-success"
                    : verificationOutcome.match_check === "FAILED"
                    ? "eg-badge-danger"
                    : "eg-badge-warning"
                }`}
              >
                {verificationOutcome.match_check.replace("_", " ")}
              </span>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Review Check</div>
              <span
                className={`eg-badge ${
                  verificationOutcome.review_completed
                    ? "eg-badge-success"
                    : "eg-badge-warning"
                }`}
              >
                {verificationOutcome.review_check.replace("_", " ")}
              </span>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>OCR Confidence</div>
              <div>
                {verificationOutcome.ocr_avg_confidence != null
                  ? `${verificationOutcome.ocr_avg_confidence.toFixed(1)}%`
                  : "—"}
              </div>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Match Status</div>
              <div>
                {verificationOutcome.match_status
                  ? verificationOutcome.match_status.replace("_", " ")
                  : "—"}
              </div>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Student</div>
              <div>
                {verificationOutcome.student_id
                  ? `ID ${verificationOutcome.student_id}`
                  : "—"}
              </div>
            </div>
          </div>

          {verificationOutcome.reasoning && (
            <div className="glass-surface glass p-4 mb-6">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "8px" }}>Reasoning</div>
              <p>{verificationOutcome.reasoning}</p>
            </div>
          )}
        </div>
      </AppShell>
    );
  }

  if (showMatch && matchResult) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <button
              onClick={() => {
                setShowMatch(false);
                setMatchResult(null);
              }}
              className="eg-btn mb-4"
            >
              ← Back to Documents
            </button>
            <h1 className="eg-page-title">Hall Ticket Match Result</h1>
            <p className="eg-page-desc">
              Document #{matchResult.document_id} ·{" "}
              <span
                className={`eg-badge ${
                  matchResult.overall_status === "MATCHED"
                    ? "eg-badge-success"
                    : matchResult.overall_status === "PARTIAL_MATCH"
                    ? "eg-badge-warning"
                    : matchResult.overall_status === "NOT_FOUND"
                    ? "eg-badge-danger"
                    : "eg-badge-neutral"
                }`}
              >
                {matchResult.overall_status.replace("_", " ")}
              </span>
            </p>
          </div>

          <div className="eg-grid-4 mb-8">
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Student</div>
              <div>{matchResult.student_id ? `ID ${matchResult.student_id}` : "—"}</div>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Exam</div>
              <div>{matchResult.exam_id ? `ID ${matchResult.exam_id}` : "—"}</div>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Registration</div>
              <div>{matchResult.registration_id ? `ID ${matchResult.registration_id}` : "—"}</div>
            </div>
            <div className="glass-surface glass p-4">
              <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Seat Assignment</div>
              <div>{matchResult.seat_assignment_id ? `ID ${matchResult.seat_assignment_id}` : "—"}</div>
            </div>
          </div>

          <h2 className="eg-page-title text-xl mb-4">Verification Signals</h2>
          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Extracted</th>
                  <th>Expected</th>
                  <th>Match</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {matchResult.signals.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 500 }}>
                      {s.field_name.replace("_", " ")}
                    </td>
                    <td>{s.extracted_value || <span style={{ color: "var(--text-muted)" }}>—</span>}</td>
                    <td>{s.expected_value || <span style={{ color: "var(--text-muted)" }}>—</span>}</td>
                    <td>
                      {s.matched ? (
                        <span className="eg-badge eg-badge-success">Match</span>
                      ) : (
                        <span className="eg-badge eg-badge-danger">Mismatch</span>
                      )}
                    </td>
                    <td style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {s.details || "—"}
                    </td>
                  </tr>
                ))}
                {matchResult.signals.length === 0 && (
                  <tr>
                    <td colSpan={5} className="text-center" style={{ padding: "2rem", color: "var(--text-muted)" }}>
                      No signals recorded
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </AppShell>
    );
  }

  if (showExtraction && extractionResult) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <button
              onClick={() => {
                setShowExtraction(false);
                setExtractionResult(null);
              }}
              className="eg-btn mb-4"
            >
              ← Back to Documents
            </button>
            <h1 className="eg-page-title">Extraction Results</h1>
            <p className="eg-page-desc">
              Document #{extractionResult.document_id} · {extractionResult.ocr_engine} ·{" "}
              {extractionResult.ocr_avg_confidence.toFixed(1)}% confidence
              {extractionResult.processing_time_ms && (
                <> · {extractionResult.processing_time_ms}ms</>
              )}
            </p>
          </div>

          <div className="eg-table-wrap">
            <table className="eg-table">
              <thead>
                <tr>
                  <th>Field</th>
                  <th>Value</th>
                  <th>OCR Conf</th>
                  <th>Method</th>
                  <th>Label</th>
                  <th>Pattern</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {extractionResult.fields.map((f) => (
                  <tr key={f.id}>
                    <td style={{ fontWeight: 500 }}>
                      {f.field_name.replace("_", " ")}
                    </td>
                    <td>
                      {f.extracted_value || <span style={{ color: "var(--text-muted)" }}>—</span>}
                    </td>
                    <td style={{ color: "var(--text-muted)" }}>
                      {f.ocr_confidence != null ? `${f.ocr_confidence.toFixed(1)}%` : "—"}
                    </td>
                    <td style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {f.extraction_method || "—"}
                    </td>
                    <td>
                      {f.label_found === true ? (
                        <span style={{ color: "var(--success, #22c55e)" }}>Yes</span>
                      ) : f.label_found === false ? (
                        <span style={{ color: "var(--danger, #ef4444)" }}>No</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {f.pattern_match === true ? (
                        <span style={{ color: "var(--success, #22c55e)" }}>Yes</span>
                      ) : f.pattern_match === false ? (
                        <span style={{ color: "var(--danger, #ef4444)" }}>No</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      <span
                        className={`eg-badge ${
                          f.review_status === "AUTO_APPROVED"
                            ? "eg-badge-success"
                            : f.review_status === "REVIEW_REQUIRED"
                            ? "eg-badge-warning"
                            : "eg-badge-info"
                        }`}
                      >
                        {f.review_status.replace("_", " ")}
                      </span>
                    </td>
                  </tr>
                ))}
                {extractionResult.fields.length === 0 && (
                  <tr>
                    <td colSpan={7} className="text-center" style={{ padding: "2rem", color: "var(--text-muted)" }}>
                      No fields extracted
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <p className="eg-breadcrumb">HOME / DOCUMENTS</p>
          <h1 className="eg-page-title">Documents</h1>
          <p className="eg-page-desc">Upload and manage examination documents</p>
        </div>

        <div className="glass-surface glass p-6 mb-6">
          <h2 className="eg-page-title text-lg mb-4">Upload Document</h2>
          {message && <p className="eg-alert eg-alert-success mb-4">{message}</p>}
          {error && <p className="eg-alert eg-alert-danger mb-4">{error}</p>}
          <div className="flex gap-4 items-center">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="eg-select"
            >
              <option value="HALL_TICKET">Hall Ticket</option>
            </select>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="eg-input"
            />
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="eg-btn eg-btn-primary"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </div>

        <div className="eg-table-wrap">
          <table className="eg-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Status</th>
                <th>Uploaded</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id}>
                  <td>{d.original_filename}</td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {d.document_type.replace("_", " ")}
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {formatSize(d.file_size)}
                  </td>
                  <td>
                    <span className="eg-badge eg-badge-info">
                      {d.status.replace("_", " ")}
                    </span>
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td>
                    <div className="flex gap-2">
                      {d.status === "PROCESSED" || d.status === "REVIEW_REQUIRED" ? (
                        <>
                          <button
                            onClick={() => handleViewExtraction(d.id)}
                            className="eg-btn text-xs"
                          >
                            View Extraction
                          </button>
                          {d.status === "REVIEW_REQUIRED" && (
                            <button
                              onClick={() => handleStartReview(d.id)}
                              disabled={reviewingId === d.id}
                              className="eg-btn eg-btn-warning text-xs"
                              style={{ opacity: reviewingId === d.id ? 0.3 : 1 }}
                            >
                              {reviewingId === d.id ? "Loading..." : "Review"}
                            </button>
                          )}
                          <button
                            onClick={() => handleMatch(d.id)}
                            disabled={matchingId === d.id}
                            className="eg-btn eg-btn-primary text-xs"
                            style={{ opacity: matchingId === d.id ? 0.3 : 1 }}
                          >
                            {matchingId === d.id ? "Matching..." : "Match Hall Ticket"}
                          </button>
                          <button
                            onClick={() => handleVerify(d.id)}
                            disabled={verifyingId === d.id}
                            className="eg-btn text-xs"
                            style={{ opacity: verifyingId === d.id ? 0.3 : 1 }}
                          >
                            {verifyingId === d.id ? "Verifying..." : "Verify"}
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleProcess(d.id)}
                          disabled={processingId === d.id}
                          className="eg-btn eg-btn-primary text-xs"
                          style={{ opacity: processingId === d.id ? 0.3 : 1 }}
                        >
                          {processingId === d.id ? "Processing..." : "Process"}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {documents.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="eg-empty">
                      <p className="eg-empty-title">No documents uploaded</p>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="eg-pagination">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn eg-btn-sm"
            >
              Previous
            </button>
            <span className="eg-pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn eg-btn-sm"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
