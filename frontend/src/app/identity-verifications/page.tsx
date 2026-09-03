"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface IdentityVerification {
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

interface ListResponse {
  items: IdentityVerification[];
  total: number;
  page: number;
  page_size: number;
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

export default function IdentityVerificationsPage() {
  const [attempts, setAttempts] = useState<IdentityVerification[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [decisionFilter, setDecisionFilter] = useState("");
  const [studentFilter, setStudentFilter] = useState("");

  const fetchAttempts = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (statusFilter) params.set("status", statusFilter);
    if (decisionFilter) params.set("decision", decisionFilter);
    if (studentFilter) params.set("student_id", studentFilter);
    const res = await fetch(`${API}/api/v1/identity-verifications?${params}`);
    const data: ListResponse = await res.json();
    setAttempts(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchAttempts();
  }, [page, statusFilter, decisionFilter, studentFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Identity Verifications
        </h1>
        <p className="text-[#999] mb-8">
          Track identity verification attempts — manual, face, or document-based
        </p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Student ID..."
            value={studentFilter}
            onChange={(e) => {
              setStudentFilter(e.target.value);
              setPage(1);
            }}
            className="w-40 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">All statuses</option>
            <option value="CREATED">Created</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="COMPLETED">Completed</option>
            <option value="FAILED">Failed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
          <select
            value={decisionFilter}
            onChange={(e) => {
              setDecisionFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
          >
            <option value="">All decisions</option>
            <option value="PENDING">Pending</option>
            <option value="MATCH">Match</option>
            <option value="NO_MATCH">No Match</option>
            <option value="INCONCLUSIVE">Inconclusive</option>
          </select>
        </div>

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">ID</th>
                <th className="px-6 py-3">Student</th>
                <th className="px-6 py-3">Registration</th>
                <th className="px-6 py-3">Method</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Decision</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {attempts.map((a) => (
                <tr
                  key={a.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{a.id}</td>
                  <td className="px-6 py-3 text-sm">#{a.student_id}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    #{a.exam_registration_id}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {a.verification_method}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        STATUS_COLORS[a.status] || "bg-gray-500/20 text-gray-400"
                      }`}
                    >
                      {a.status}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        DECISION_COLORS[a.decision] || "bg-gray-500/20 text-gray-400"
                      }`}
                    >
                      {a.decision}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-[#666]">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <Link
                      href={`/identity-verifications/${a.id}`}
                      className="text-cyan-400 hover:text-cyan-300 text-sm"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {attempts.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No identity verification attempts found
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
