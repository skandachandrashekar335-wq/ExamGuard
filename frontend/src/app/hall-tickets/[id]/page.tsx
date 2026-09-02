"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

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

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATUS_COLORS: Record<string, string> = {
  CREATED: "bg-blue-500/20 text-blue-400",
  EXTRACTED: "bg-cyan-500/20 text-cyan-400",
  MATCHED: "bg-indigo-500/20 text-indigo-400",
  VERIFIED: "bg-emerald-500/20 text-emerald-400",
  REJECTED: "bg-red-500/20 text-red-400",
  CANCELLED: "bg-gray-500/20 text-gray-400",
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
    const res = await fetch(`${API}/api/v1/hall-tickets/${id}/detailed`);
    if (!res.ok) {
      setError("Hall ticket not found");
      return;
    }
    const json: DetailedResponse = await res.json();
    setData(json);
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const approve = async () => {
    setActionMsg("");
    const res = await fetch(`${API}/api/v1/hall-tickets/${id}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (res.ok) {
      setActionMsg("Hall ticket approved");
      fetchDetail();
    } else {
      const err = await res.json();
      setActionMsg(err.detail || "Failed to approve");
    }
  };

  const reject = async () => {
    if (!rejectReason) {
      setActionMsg("Rejection reason is required");
      return;
    }
    setActionMsg("");
    const res = await fetch(`${API}/api/v1/hall-tickets/${id}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason: rejectReason }),
    });
    if (res.ok) {
      setActionMsg("Hall ticket rejected");
      setRejectReason("");
      fetchDetail();
    } else {
      const err = await res.json();
      setActionMsg(err.detail || "Failed to reject");
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-[#050505] text-white p-8">
        <div className="max-w-4xl mx-auto">
          <p className="text-pink-400">{error}</p>
          <Link
            href="/hall-tickets"
            className="text-cyan-400 hover:text-cyan-300 mt-4 inline-block"
          >
            &larr; Back to list
          </Link>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#050505] text-white p-8">
        <div className="max-w-4xl mx-auto text-[#666]">Loading...</div>
      </div>
    );
  }

  const ht = data.hall_ticket;
  const currentIdx = STATUS_FLOW.indexOf(ht.status);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-4xl mx-auto">
        <Link
          href="/hall-tickets"
          className="text-cyan-400 hover:text-cyan-300 text-sm mb-6 inline-block"
        >
          &larr; Back to hall tickets
        </Link>

        <div className="flex items-center gap-4 mb-6">
          <h1 className="text-3xl font-bold uppercase tracking-wider">
            Hall Ticket #{ht.id}
          </h1>
          <span
            className={`text-xs px-3 py-1 rounded-full font-medium ${
              STATUS_COLORS[ht.status] || "bg-gray-500/20 text-gray-400"
            }`}
          >
            {ht.status}
          </span>
        </div>

        {/* Lifecycle progress */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
            Lifecycle
          </h2>
          <div className="flex items-center gap-2">
            {STATUS_FLOW.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${
                    i <= currentIdx
                      ? "bg-cyan-500 text-white"
                      : "bg-[#222] text-[#666]"
                  }`}
                >
                  {i + 1}
                </div>
                <span
                  className={`text-xs ${
                    i <= currentIdx ? "text-white" : "text-[#666]"
                  }`}
                >
                  {s}
                </span>
                {i < STATUS_FLOW.length - 1 && (
                  <div
                    className={`w-8 h-0.5 ${
                      i < currentIdx ? "bg-cyan-500" : "bg-[#222]"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Student info */}
          <div className="bg-[#111] border border-white/10 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
              Student
            </h2>
            {data.student ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-[#666]">USN:</span>{" "}
                  <span className="font-mono">{data.student.usn}</span>
                </p>
                <p>
                  <span className="text-[#666]">Name:</span>{" "}
                  {data.student.name}
                </p>
                <p>
                  <span className="text-[#666]">Student ID:</span>{" "}
                  {data.student.id}
                </p>
              </div>
            ) : (
              <p className="text-[#666] text-sm">No student linked</p>
            )}
          </div>

          {/* Exam info */}
          <div className="bg-[#111] border border-white/10 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
              Exam
            </h2>
            {data.exam ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-[#666]">Exam ID:</span>{" "}
                  {data.exam.id}
                </p>
                <p>
                  <span className="text-[#666]">Subject ID:</span>{" "}
                  {data.exam.subject_id}
                </p>
                <p>
                  <span className="text-[#666]">Date:</span>{" "}
                  {data.exam.exam_date}
                </p>
                <p>
                  <span className="text-[#666]">Time:</span>{" "}
                  {data.exam.start_time} &ndash; {data.exam.end_time}
                </p>
              </div>
            ) : (
              <p className="text-[#666] text-sm">No exam linked</p>
            )}
          </div>
        </div>

        {/* Document info */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
            Source Document
          </h2>
          {data.document ? (
            <div className="space-y-2 text-sm">
              <p>
                <span className="text-[#666]">Filename:</span>{" "}
                {data.document.original_filename}
              </p>
              <p>
                <span className="text-[#666]">Type:</span>{" "}
                {data.document.content_type}
              </p>
              <p>
                <span className="text-[#666]">Size:</span>{" "}
                {(data.document.file_size / 1024).toFixed(1)} KB
              </p>
              <p>
                <span className="text-[#666]">Status:</span>{" "}
                {data.document.status}
              </p>
            </div>
          ) : (
            <p className="text-[#666] text-sm">
              No document uploaded yet. Upload a hall-ticket PDF and link it via
              the API.
            </p>
          )}
        </div>

        {/* Linked resources */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
            Linked Resources
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-[#666] block">Registration</span>
              <span className="font-mono">
                #{ht.exam_registration_id}
              </span>
            </div>
            <div>
              <span className="text-[#666] block">Document</span>
              <span className="font-mono">
                {ht.document_id ? `#${ht.document_id}` : "—"}
              </span>
            </div>
            <div>
              <span className="text-[#666] block">Extraction</span>
              <span className="font-mono">
                {ht.extraction_result_id
                  ? `#${ht.extraction_result_id}`
                  : "—"}
              </span>
            </div>
            <div>
              <span className="text-[#666] block">Match</span>
              <span className="font-mono">
                {ht.match_result_id ? `#${ht.match_result_id}` : "—"}
              </span>
            </div>
          </div>
        </div>

        {ht.rejection_reason && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6 mb-6">
            <h2 className="text-sm font-semibold text-red-400 uppercase tracking-wider mb-2">
              Rejection Reason
            </h2>
            <p className="text-sm text-red-300">{ht.rejection_reason}</p>
          </div>
        )}

        {/* Admin actions */}
        {ht.status !== "VERIFIED" &&
          ht.status !== "REJECTED" &&
          ht.status !== "CANCELLED" && (
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">
                Admin Actions
              </h2>
              {actionMsg && (
                <p
                  className={`text-sm mb-4 ${
                    actionMsg.includes("Failed") || actionMsg.includes("required")
                      ? "text-pink-400"
                      : "text-emerald-400"
                  }`}
                >
                  {actionMsg}
                </p>
              )}
              <div className="flex gap-4 items-end">
                <button
                  onClick={approve}
                  className="bg-emerald-600 hover:bg-emerald-500 px-6 py-2 rounded-lg font-medium text-sm"
                >
                  Approve (Verify)
                </button>
                <div className="flex-1">
                  <input
                    type="text"
                    placeholder="Rejection reason..."
                    value={rejectReason}
                    onChange={(e) => setRejectReason(e.target.value)}
                    className="w-full bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white text-sm placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
                  />
                </div>
                <button
                  onClick={reject}
                  className="bg-red-600 hover:bg-red-500 px-6 py-2 rounded-lg font-medium text-sm"
                >
                  Reject
                </button>
              </div>
            </div>
          )}

        <div className="mt-6 text-sm text-[#666]">
          Created: {new Date(ht.created_at).toLocaleString()} &middot; Updated:{" "}
          {new Date(ht.updated_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}
