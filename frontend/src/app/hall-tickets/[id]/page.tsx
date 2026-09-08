"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";

interface HallTicket {
  id: number;
  exam_registration_id: number;
  document_id: number | null;
  extraction_result_id: number | null;
  match_result_id: number | null;
  verification_outcome_id: number | null;
  status: string;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

interface StudentInfo {
  id: number;
  usn: string;
  name: string;
}

interface ExamInfo {
  id: number;
  subject_id: number;
  exam_date: string;
  start_time: string;
  end_time: string;
}

interface DetailedResponse {
  hall_ticket: HallTicket;
  student: StudentInfo | null;
  exam: ExamInfo | null;
  document: {
    id: number;
    original_filename: string;
    content_type: string;
    file_size: number;
    status: string;
  } | null;
}

const STATUS_BADGE: Record<string, string> = {
  CREATED: "eg-badge-info",
  EXTRACTED: "eg-badge-info",
  MATCHED: "eg-badge-info",
  VERIFIED: "eg-badge-success",
  REJECTED: "eg-badge-danger",
  CANCELLED: "eg-badge-neutral",
};

const STATUS_FLOW = ["CREATED", "EXTRACTED", "MATCHED", "VERIFIED"];

export default function HallTicketDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<DetailedResponse | null>(null);
  const [error, setError] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const fetchDetail = async () => {
    try {
      const json = await apiRequest<DetailedResponse>(`/api/v1/hall-tickets/${id}/detailed`);
      setData(json);
    } catch {
      setError("Hall ticket not found");
    }
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const approve = async () => {
    setActionMsg("");
    try {
      await apiRequest(`/api/v1/hall-tickets/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setActionMsg("Hall ticket approved");
      fetchDetail();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Failed to approve");
    }
  };

  const reject = async () => {
    if (!rejectReason) {
      setActionMsg("Rejection reason is required");
      return;
    }
    setActionMsg("");
    try {
      await apiRequest(`/api/v1/hall-tickets/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason: rejectReason }),
      });
      setActionMsg("Hall ticket rejected");
      setRejectReason("");
      fetchDetail();
    } catch (err) {
      setActionMsg(err instanceof Error ? err.message : "Failed to reject");
    }
  };

  if (error) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>
            <Link href="/hall-tickets" className="eg-breadcrumb mt-4 inline-block">
              ← Back to list
            </Link>
          </div>
        </div>
      </AppShell>
    );
  }

  if (!data) {
    return (
      <AppShell>
        <div className="eg-page">
          <div className="eg-page-header">
            <span className="eg-mono text-[var(--text-muted)]">Loading...</span>
          </div>
        </div>
      </AppShell>
    );
  }

  const ht = data.hall_ticket;
  const currentIdx = STATUS_FLOW.indexOf(ht.status);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/hall-tickets" className="eg-breadcrumb">
            ← Hall Tickets
          </Link>
          <div className="flex items-center gap-4">
            <h1 className="eg-page-title">Hall Ticket #{ht.id}</h1>
            <span className={`eg-badge ${STATUS_BADGE[ht.status] || "eg-badge-neutral"}`}>
              {ht.status}
            </span>
          </div>
        </div>

        {/* Lifecycle progress */}
        <div className="glass-surface p-6 mb-6">
          <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
            LIFECYCLE
          </h2>
          <div className="flex items-center gap-2">
            {STATUS_FLOW.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    i <= currentIdx
                      ? "text-white"
                      : "text-[var(--text-muted)]"
                  }`}
                  style={{
                    background: i <= currentIdx ? "var(--accent)" : "var(--border)",
                  }}
                >
                  {i + 1}
                </div>
                <span
                  className={`text-xs ${
                    i <= currentIdx
                      ? "text-[var(--text-primary)]"
                      : "text-[var(--text-muted)]"
                  }`}
                >
                  {s}
                </span>
                {i < STATUS_FLOW.length - 1 && (
                  <div
                    className="w-8 h-0.5"
                    style={{
                      background: i < currentIdx ? "var(--accent)" : "var(--border)",
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Student info */}
          <div className="glass-surface p-6">
            <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
              STUDENT
            </h2>
            {data.student ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-[var(--text-secondary)]">USN:</span>{" "}
                  <span style={{ fontFamily: "var(--font-mono)" }}>
                    {data.student.usn}
                  </span>
                </p>
                <p>
                  <span className="text-[var(--text-secondary)]">Name:</span>{" "}
                  {data.student.name}
                </p>
                <p>
                  <span className="text-[var(--text-secondary)]">Student ID:</span>{" "}
                  {data.student.id}
                </p>
              </div>
            ) : (
              <p className="text-[var(--text-muted)] text-sm">No student linked</p>
            )}
          </div>

          {/* Exam info */}
          <div className="glass-surface p-6">
            <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
              EXAM
            </h2>
            {data.exam ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-[var(--text-secondary)]">Exam ID:</span>{" "}
                  {data.exam.id}
                </p>
                <p>
                  <span className="text-[var(--text-secondary)]">Subject ID:</span>{" "}
                  {data.exam.subject_id}
                </p>
                <p>
                  <span className="text-[var(--text-secondary)]">Date:</span>{" "}
                  {data.exam.exam_date}
                </p>
                <p>
                  <span className="text-[var(--text-secondary)]">Time:</span>{" "}
                  {data.exam.start_time} &ndash; {data.exam.end_time}
                </p>
              </div>
            ) : (
              <p className="text-[var(--text-muted)] text-sm">No exam linked</p>
            )}
          </div>
        </div>

        {/* Document info */}
        <div className="glass-surface p-6 mb-6">
          <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
            SOURCE DOCUMENT
          </h2>
          {data.document ? (
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-[var(--text-secondary)]">Filename:</span>{" "}
                {data.document.original_filename}
              </p>
              <p>
                <span className="text-[var(--text-secondary)]">Type:</span>{" "}
                {data.document.content_type}
              </p>
              <p>
                <span className="text-[var(--text-secondary)]">Size:</span>{" "}
                {(data.document.file_size / 1024).toFixed(1)} KB
              </p>
              <p>
                <span className="text-[var(--text-secondary)]">Status:</span>{" "}
                {data.document.status}
              </p>
            </div>
          ) : (
            <p className="text-[var(--text-muted)] text-sm">
              No document uploaded yet. Upload a hall-ticket PDF and link it via
              the API.
            </p>
          )}
        </div>

        {/* Linked resources */}
        <div className="glass-surface p-6 mb-6">
          <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
            LINKED RESOURCES
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-[var(--text-secondary)] block">Registration</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>
                #{ht.exam_registration_id}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)] block">Document</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {ht.document_id ? `#${ht.document_id}` : "—"}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)] block">Extraction</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {ht.extraction_result_id
                  ? `#${ht.extraction_result_id}`
                  : "—"}
              </span>
            </div>
            <div>
              <span className="text-[var(--text-secondary)] block">Match</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {ht.match_result_id ? `#${ht.match_result_id}` : "—"}
              </span>
            </div>
          </div>
        </div>

        {ht.rejection_reason && (
          <div className="glass-surface p-6 mb-6" style={{ borderColor: "rgba(220,38,38,0.3)" }}>
            <h2 className="eg-mono-sm mb-2" style={{ color: "var(--danger)" }}>
              REJECTION REASON
            </h2>
            <p className="text-sm" style={{ color: "var(--danger)" }}>
              {ht.rejection_reason}
            </p>
          </div>
        )}

        {/* Admin actions */}
        {ht.status !== "VERIFIED" &&
          ht.status !== "REJECTED" &&
          ht.status !== "CANCELLED" && (
            <div className="glass-surface p-6">
              <h2 className="eg-mono-sm text-[var(--text-muted)] mb-4">
                ADMIN ACTIONS
              </h2>
              {actionMsg && (
                <p
                  className="text-sm mb-4"
                  style={{
                    color: actionMsg.includes("Failed") || actionMsg.includes("required")
                      ? "var(--danger)"
                      : "var(--success)",
                  }}
                >
                  {actionMsg}
                </p>
              )}
              <div className="flex gap-4 items-end">
                <button
                  onClick={approve}
                  className="eg-btn eg-btn-primary px-6 py-2 text-sm"
                >
                  Approve (Verify)
                </button>
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="Rejection reason..."
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="eg-input w-full"
                  />
                </div>
                <button
                  onClick={reject}
                  className="eg-btn eg-btn-danger px-6 py-2 text-sm"
                >
                  Reject
                </button>
              </div>
            </div>
          )}

        <div className="mt-6 text-sm text-[var(--text-muted)]">
          Created: {new Date(ht.created_at).toLocaleString()} &middot; Updated:{" "}
          {new Date(ht.updated_at).toLocaleString()}
        </div>
      </div>
    </AppShell>
  );
}
