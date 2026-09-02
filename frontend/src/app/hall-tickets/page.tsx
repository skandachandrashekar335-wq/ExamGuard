"use client";

import { useEffect, useState } from "react";
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

interface ListResponse {
  items: HallTicket[];
  total: number;
  page: number;
  page_size: number;
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

export default function HallTicketsPage() {
  const [tickets, setTickets] = useState<HallTicket[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [usnSearch, setUsnSearch] = useState("");
  const [useSearch, setUseSearch] = useState(false);

  const fetchTickets = async () => {
    if (useSearch && usnSearch) {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        usn: usnSearch,
      });
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(`${API}/api/v1/hall-tickets/search?${params}`);
      const data: ListResponse = await res.json();
      setTickets(data.items);
      setTotal(data.total);
    } else {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(`${API}/api/v1/hall-tickets?${params}`);
      const data: ListResponse = await res.json();
      setTickets(data.items);
      setTotal(data.total);
    }
  };

  useEffect(() => {
    fetchTickets();
  }, [page, statusFilter, useSearch, usnSearch]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Hall Tickets
        </h1>
        <p className="text-[#999] mb-8">
          Manage hall ticket lifecycle — upload, extract, match, verify, approve
          or reject
        </p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by USN..."
            value={usnSearch}
            onChange={(e) => {
              setUsnSearch(e.target.value);
              setUseSearch(e.target.value.length > 0);
              setPage(1);
            }}
            className="flex-1 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
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
            <option value="EXTRACTED">Extracted</option>
            <option value="MATCHED">Matched</option>
            <option value="VERIFIED">Verified</option>
            <option value="REJECTED">Rejected</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </div>

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">ID</th>
                <th className="px-6 py-3">Registration</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Document</th>
                <th className="px-6 py-3">Extraction</th>
                <th className="px-6 py-3">Match</th>
                <th className="px-6 py-3">Verification</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr
                  key={t.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{t.id}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    #{t.exam_registration_id}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        STATUS_COLORS[t.status] || "bg-gray-500/20 text-gray-400"
                      }`}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {t.document_id ? `#${t.document_id}` : "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {t.extraction_result_id ? `#${t.extraction_result_id}` : "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {t.match_result_id ? `#${t.match_result_id}` : "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {t.verification_outcome_id
                      ? `#${t.verification_outcome_id}`
                      : "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#666]">
                    {new Date(t.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3 text-right">
                    <Link
                      href={`/hall-tickets/${t.id}`}
                      className="text-cyan-400 hover:text-cyan-300 text-sm"
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {tickets.length === 0 && (
                <tr>
                  <td
                    colSpan={9}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No hall tickets found
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
