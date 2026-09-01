"use client";

import { useEffect, useState } from "react";

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

  if (showMatch && matchResult) {
    return (
      <div className="min-h-screen bg-[#050505] text-white p-8">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => {
              setShowMatch(false);
              setMatchResult(null);
            }}
            className="text-cyan-400 hover:text-cyan-300 mb-6 text-sm"
          >
            &larr; Back to Documents
          </button>

          <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
            Hall Ticket Match Result
          </h1>
          <p className="text-[#999] mb-8">
            Document #{matchResult.document_id} &middot;{" "}
            <span
              className={`px-2 py-1 rounded-full text-xs ${
                matchResult.overall_status === "MATCHED"
                  ? "bg-emerald-500/20 text-emerald-400"
                  : matchResult.overall_status === "PARTIAL_MATCH"
                  ? "bg-amber-500/20 text-amber-400"
                  : matchResult.overall_status === "NOT_FOUND"
                  ? "bg-pink-500/20 text-pink-400"
                  : "bg-red-500/20 text-red-400"
              }`}
            >
              {matchResult.overall_status.replace("_", " ")}
            </span>
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-[#111] border border-white/10 rounded-lg p-4">
              <div className="text-xs text-[#666] mb-1">Student</div>
              <div className="text-sm">
                {matchResult.student_id ? `ID ${matchResult.student_id}` : "—"}
              </div>
            </div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4">
              <div className="text-xs text-[#666] mb-1">Exam</div>
              <div className="text-sm">
                {matchResult.exam_id ? `ID ${matchResult.exam_id}` : "—"}
              </div>
            </div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4">
              <div className="text-xs text-[#666] mb-1">Registration</div>
              <div className="text-sm">
                {matchResult.registration_id ? `ID ${matchResult.registration_id}` : "—"}
              </div>
            </div>
            <div className="bg-[#111] border border-white/10 rounded-lg p-4">
              <div className="text-xs text-[#666] mb-1">Seat Assignment</div>
              <div className="text-sm">
                {matchResult.seat_assignment_id ? `ID ${matchResult.seat_assignment_id}` : "—"}
              </div>
            </div>
          </div>

          <h2 className="text-xl font-semibold mb-4">Verification Signals</h2>
          <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                  <th className="px-6 py-3">Field</th>
                  <th className="px-6 py-3">Extracted</th>
                  <th className="px-6 py-3">Expected</th>
                  <th className="px-6 py-3">Match</th>
                  <th className="px-6 py-3">Details</th>
                </tr>
              </thead>
              <tbody>
                {matchResult.signals.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-white/5 hover:bg-white/[0.02]"
                  >
                    <td className="px-6 py-3 text-sm font-medium">
                      {s.field_name.replace("_", " ")}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {s.extracted_value || (
                        <span className="text-[#666]">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {s.expected_value || (
                        <span className="text-[#666]">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      {s.matched ? (
                        <span className="text-emerald-400 text-xs px-2 py-1 rounded-full bg-emerald-500/20">
                          Match
                        </span>
                      ) : (
                        <span className="text-pink-400 text-xs px-2 py-1 rounded-full bg-pink-500/20">
                          Mismatch
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-xs text-[#999]">
                      {s.details || "—"}
                    </td>
                  </tr>
                ))}
                {matchResult.signals.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-[#666]">
                      No signals recorded
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (showExtraction && extractionResult) {
    return (
      <div className="min-h-screen bg-[#050505] text-white p-8">
        <div className="max-w-5xl mx-auto">
          <button
            onClick={() => {
              setShowExtraction(false);
              setExtractionResult(null);
            }}
            className="text-cyan-400 hover:text-cyan-300 mb-6 text-sm"
          >
            &larr; Back to Documents
          </button>

          <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
            Extraction Results
          </h1>
          <p className="text-[#999] mb-8">
            Document #{extractionResult.document_id} &middot; {extractionResult.ocr_engine} &middot;{" "}
            {extractionResult.ocr_avg_confidence.toFixed(1)}% confidence
            {extractionResult.processing_time_ms && (
              <> &middot; {extractionResult.processing_time_ms}ms</>
            )}
          </p>

          <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                  <th className="px-6 py-3">Field</th>
                  <th className="px-6 py-3">Value</th>
                  <th className="px-6 py-3">OCR Conf</th>
                  <th className="px-6 py-3">Method</th>
                  <th className="px-6 py-3">Label</th>
                  <th className="px-6 py-3">Pattern</th>
                  <th className="px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {extractionResult.fields.map((f) => (
                  <tr
                    key={f.id}
                    className="border-b border-white/5 hover:bg-white/[0.02]"
                  >
                    <td className="px-6 py-3 text-sm font-medium">
                      {f.field_name.replace("_", " ")}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {f.extracted_value || (
                        <span className="text-[#666]">—</span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm text-[#999]">
                      {f.ocr_confidence != null
                        ? `${f.ocr_confidence.toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="px-6 py-3 text-xs text-[#999]">
                      {f.extraction_method || "—"}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {f.label_found === true ? (
                        <span className="text-emerald-400">Yes</span>
                      ) : f.label_found === false ? (
                        <span className="text-pink-400">No</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-6 py-3 text-sm">
                      {f.pattern_match === true ? (
                        <span className="text-emerald-400">Yes</span>
                      ) : f.pattern_match === false ? (
                        <span className="text-pink-400">No</span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`text-xs px-2 py-1 rounded-full ${
                          f.review_status === "AUTO_APPROVED"
                            ? "bg-emerald-500/20 text-emerald-400"
                            : f.review_status === "REVIEW_REQUIRED"
                            ? "bg-amber-500/20 text-amber-400"
                            : "bg-cyan-500/20 text-cyan-400"
                        }`}
                      >
                        {f.review_status.replace("_", " ")}
                      </span>
                    </td>
                  </tr>
                ))}
                {extractionResult.fields.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-[#666]">
                      No fields extracted
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Documents
        </h1>
        <p className="text-[#999] mb-8">Upload and manage examination documents</p>

        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Upload Document</h2>
          {message && <p className="text-emerald-400 text-sm mb-4">{message}</p>}
          {error && <p className="text-pink-400 text-sm mb-4">{error}</p>}
          <div className="flex gap-4 items-center">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="HALL_TICKET">Hall Ticket</option>
            </select>
            <input
              type="file"
              accept=".pdf,.jpg,.jpeg,.png"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              className="text-sm text-[#999] file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-gradient-to-r file:from-cyan-500 file:to-pink-500 file:text-white file:cursor-pointer"
            />
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading}
              className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90 disabled:opacity-30"
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        </div>

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">Filename</th>
                <th className="px-6 py-3">Type</th>
                <th className="px-6 py-3">Size</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Uploaded</th>
                <th className="px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr
                  key={d.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{d.original_filename}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {d.document_type.replace("_", " ")}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {formatSize(d.file_size)}
                  </td>
                  <td className="px-6 py-3">
                    <span className="text-xs px-2 py-1 rounded-full bg-cyan-500/20 text-cyan-400">
                      {d.status.replace("_", " ")}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {new Date(d.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 text-sm flex gap-2">
                    {d.status === "PROCESSED" || d.status === "REVIEW_REQUIRED" ? (
                      <>
                        <button
                          onClick={() => handleViewExtraction(d.id)}
                          className="text-cyan-400 hover:text-cyan-300 text-xs"
                        >
                          View Extraction
                        </button>
                        <button
                          onClick={() => handleMatch(d.id)}
                          disabled={matchingId === d.id}
                          className="text-emerald-400 hover:text-emerald-300 text-xs disabled:opacity-30"
                        >
                          {matchingId === d.id ? "Matching..." : "Match Hall Ticket"}
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => handleProcess(d.id)}
                        disabled={processingId === d.id}
                        className="text-emerald-400 hover:text-emerald-300 text-xs disabled:opacity-30"
                      >
                        {processingId === d.id ? "Processing..." : "Process"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {documents.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-[#666]">
                    No documents uploaded
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex justify-center gap-4 mt-6">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Previous
            </button>
            <span className="py-2 text-sm text-[#999]">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="border border-white/20 px-4 py-2 rounded-lg disabled:opacity-30 hover:bg-white/5"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
