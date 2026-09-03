"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

interface Attempt {
  id: number;
  student_id: number;
  exam_registration_id: number;
  hall_ticket_id: number | null;
  status: string;
  verification_method: string;
  decision: string;
  failure_reason: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

interface Evidence {
  id: number;
  attempt_id: number;
  signal_type: string;
  signal_value: string | null;
  provider_name: string | null;
  provider_version: string | null;
  confidence: number | null;
  details: string | null;
  created_at: string;
}

interface ContextResponse {
  attempt: Attempt;
  evidence: Evidence[];
  student: { id: number; usn: string; name: string } | null;
  exam: { id: number; subject_id: number; exam_name: string } | null;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const STATUS_COLORS: Record<string, string> = {
  CREATED: "bg-blue-500/20 text-blue-400",
  IN_PROGRESS: "bg-cyan-500/20 text-cyan-400",
  COMPLETED: "bg-emerald-500/20 text-emerald-400",
  FAILED: "bg-red-500/20 text-red-400",
  CANCELLED: "bg-gray-500/20 text-gray-400",
};

const DECISION_COLORS: Record<string, string> = {
  PENDING: "bg-yellow-500/20 text-yellow-400",
  MATCH: "bg-emerald-500/20 text-emerald-400",
  NO_MATCH: "bg-red-500/20 text-red-400",
  INCONCLUSIVE: "bg-orange-500/20 text-orange-400",
};

const STATUS_FLOW = ["CREATED", "IN_PROGRESS", "COMPLETED"];

export default function IdentityVerificationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [data, setData] = useState<ContextResponse | null>(null);
  const [error, setError] = useState("");
  const [actionMsg, setActionMsg] = useState("");

  const fetchDetail = async () => {
    const res = await fetch(`${API}/api/v1/identity-verifications/${id}/context`);
    if (!res.ok) {
      setError("Identity verification attempt not found");
      return;
    }
    const json: ContextResponse = await res.json();
    setData(json);
  };

  useEffect(() => {
    fetchDetail();
  }, [id]);

  const startAttempt = async () => {
    setActionMsg("");
    const res = await fetch(
      `${API}/api/v1/identity-verifications/${id}/start`,
      { method: "POST" }
    );
    if (res.ok) {
      setActionMsg("Attempt started");
      fetchDetail();
    } else {
      const err = await res.json();
      setActionMsg(err.detail || "Failed to start");
    }
  };

  const evaluate = async () => {
    setActionMsg("");
    const res = await fetch(
      `${API}/api/v1/identity-verifications/${id}/evaluate`,
      { method: "POST" }
    );
    if (res.ok) {
      setActionMsg("Evidence evaluated");
      fetchDetail();
    } else {
      const err = await res.json();
      setActionMsg(err.detail || "Failed to evaluate");
    }
  };

  const cancelAttempt = async () => {
    setActionMsg("");
    const res = await fetch(
      `${API}/api/v1/identity-verifications/${id}/cancel`,
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }
    );
    if (res.ok) {
      setActionMsg("Attempt cancelled");
      fetchDetail();
    } else {
      const err = await res.json();
      setActionMsg(err.detail || "Failed to cancel");
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-[#050505] text-white p-8">
        <div className="max-w-4xl mx-auto">
          <p className="text-pink-400">{error}</p>
          <Link href="/identity-verifications" className="text-cyan-400 hover:text-cyan-300 mt-4 inline-block">
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

  const a = data.attempt;
  const currentIdx = STATUS_FLOW.indexOf(a.status);
  const isTerminal = ["COMPLETED", "FAILED", "CANCELLED"].includes(a.status);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-4xl mx-auto">
        <Link href="/identity-verifications" className="text-cyan-400 hover:text-cyan-300 text-sm mb-6 inline-block">
          &larr; Back to identity verifications
        </Link>

        <div className="flex items-center gap-4 mb-6">
          <h1 className="text-3xl font-bold uppercase tracking-wider">
            Verification #{a.id}
          </h1>
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${STATUS_COLORS[a.status] || "bg-gray-500/20 text-gray-400"}`}>
            {a.status}
          </span>
          <span className={`text-xs px-3 py-1 rounded-full font-medium ${DECISION_COLORS[a.decision] || "bg-gray-500/20 text-gray-400"}`}>
            {a.decision}
          </span>
        </div>

        {/* Lifecycle */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Lifecycle</h2>
          <div className="flex items-center gap-2">
            {STATUS_FLOW.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold ${i <= currentIdx ? "bg-cyan-500 text-white" : "bg-[#222] text-[#666]"}`}>
                  {i + 1}
                </div>
                <span className={`text-xs ${i <= currentIdx ? "text-white" : "text-[#666]"}`}>{s}</span>
                {i < STATUS_FLOW.length - 1 && (
                  <div className={`w-8 h-0.5 ${i < currentIdx ? "bg-cyan-500" : "bg-[#222]"}`} />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Student */}
          <div className="bg-[#111] border border-white/10 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Student</h2>
            {data.student ? (
              <div className="space-y-2 text-sm">
                <p><span className="text-[#666]">USN:</span> <span className="font-mono">{data.student.usn}</span></p>
                <p><span className="text-[#666]">Name:</span> {data.student.name}</p>
                <p><span className="text-[#666]">ID:</span> {data.student.id}</p>
              </div>
            ) : (
              <p className="text-[#666] text-sm">No student linked</p>
            )}
          </div>

          {/* Exam */}
          <div className="bg-[#111] border border-white/10 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Exam</h2>
            {data.exam ? (
              <div className="space-y-2 text-sm">
                <p><span className="text-[#666]">Exam:</span> {data.exam.exam_name}</p>
                <p><span className="text-[#666]">Subject ID:</span> {data.exam.subject_id}</p>
              </div>
            ) : (
              <p className="text-[#666] text-sm">No exam linked</p>
            )}
          </div>
        </div>

        {/* Attempt details */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Attempt Details</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <span className="text-[#666] block">Method</span>
              <span>{a.verification_method}</span>
            </div>
            <div>
              <span className="text-[#666] block">Registration</span>
              <span className="font-mono">#{a.exam_registration_id}</span>
            </div>
            <div>
              <span className="text-[#666] block">Hall Ticket</span>
              <span className="font-mono">{a.hall_ticket_id ? `#${a.hall_ticket_id}` : "—"}</span>
            </div>
            <div>
              <span className="text-[#666] block">Started</span>
              <span>{a.started_at ? new Date(a.started_at).toLocaleString() : "—"}</span>
            </div>
          </div>
          {a.failure_reason && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
              <span className="text-xs text-red-400">Failure/Reason:</span>
              <p className="text-sm text-red-300 mt-1">{a.failure_reason}</p>
            </div>
          )}
        </div>

        {/* Evidence */}
        <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
          <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Evidence Signals</h2>
          {data.evidence.length === 0 ? (
            <p className="text-[#666] text-sm">No evidence recorded yet</p>
          ) : (
            <div className="space-y-3">
              {data.evidence.map((e) => (
                <div key={e.id} className="bg-[#050505] border border-white/5 rounded-lg p-4 text-sm">
                  <div className="flex items-center gap-4">
                    <span className="font-mono text-cyan-400">{e.signal_type}</span>
                    <span className="text-white">{e.signal_value || "—"}</span>
                    {e.confidence !== null && (
                      <span className="text-[#999]">confidence: {e.confidence.toFixed(3)}</span>
                    )}
                    {e.provider_name && (
                      <span className="text-[#666]">{e.provider_name} {e.provider_version || ""}</span>
                    )}
                  </div>
                  {e.details && <p className="text-[#666] mt-2">{e.details}</p>}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Not biometric notice */}
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4 mb-6">
          <p className="text-sm text-blue-300">
            This is the identity verification foundation. Actual biometric face verification
            will be connected in Phase 8. Currently supports manual and deterministic
            verification methods only.
          </p>
        </div>

        {/* Actions */}
        {!isTerminal && (
          <div className="bg-[#111] border border-white/10 rounded-lg p-6">
            <h2 className="text-sm font-semibold text-[#999] uppercase tracking-wider mb-4">Actions</h2>
            {actionMsg && (
              <p className={`text-sm mb-4 ${actionMsg.includes("Failed") ? "text-pink-400" : "text-emerald-400"}`}>
                {actionMsg}
              </p>
            )}
            <div className="flex gap-4">
              {a.status === "CREATED" && (
                <button onClick={startAttempt} className="bg-cyan-600 hover:bg-cyan-500 px-4 py-2 rounded-lg text-sm font-medium">
                  Start
                </button>
              )}
              {(a.status === "CREATED" || a.status === "IN_PROGRESS") && (
                <button onClick={evaluate} className="bg-emerald-600 hover:bg-emerald-500 px-4 py-2 rounded-lg text-sm font-medium">
                  Evaluate Evidence
                </button>
              )}
              <button onClick={cancelAttempt} className="border border-white/20 px-4 py-2 rounded-lg text-sm hover:bg-white/5">
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="mt-6 text-sm text-[#666]">
          Created: {new Date(a.created_at).toLocaleString()}
          {a.completed_at && <> · Completed: {new Date(a.completed_at).toLocaleString()}</>}
        </div>
      </div>
    </div>
  );
}
