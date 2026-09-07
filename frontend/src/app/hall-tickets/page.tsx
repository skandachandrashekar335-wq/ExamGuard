"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";

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
  CREATED: "eg-badge eg-badge-info",
  EXTRACTED: "eg-badge eg-badge-info",
  MATCHED: "eg-badge eg-badge-warning",
  VERIFIED: "eg-badge eg-badge-success",
  REJECTED: "eg-badge eg-badge-danger",
  CANCELLED: "eg-badge eg-badge-neutral",
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
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <h1 className="eg-page-title">Hall Tickets</h1>
          <p className="eg-page-desc">
            Manage hall ticket lifecycle — upload, extract, match, verify, approve
            or reject
          </p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search by USN..."
            value={usnSearch}
            onChange={(e) => {
              setUsnSearch(e.target.value);
              setUseSearch(e.target.value.length > 0);
              setPage(1);
            }}
            className="eg-input flex-1"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="eg-select"
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

        <div className="eg-table-wrap">
          <table className="eg-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Registration</th>
                <th>Status</th>
                <th>Document</th>
                <th>Extraction</th>
                <th>Match</th>
                <th>Verification</th>
                <th>Created</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>#{t.exam_registration_id}</td>
                  <td>
                    <span
                      className={STATUS_COLORS[t.status] || "eg-badge eg-badge-neutral"}
                    >
                      {t.status}
                    </span>
                  </td>
                  <td>{t.document_id ? `#${t.document_id}` : "—"}</td>
                  <td>{t.extraction_result_id ? `#${t.extraction_result_id}` : "—"}</td>
                  <td>{t.match_result_id ? `#${t.match_result_id}` : "—"}</td>
                  <td>
                    {t.verification_outcome_id
                      ? `#${t.verification_outcome_id}`
                      : "—"}
                  </td>
                  <td>{new Date(t.created_at).toLocaleDateString()}</td>
                  <td style={{ textAlign: "right" }}>
                    <Link
                      href={`/hall-tickets/${t.id}`}
                      className="eg-btn eg-btn-primary"
                      style={{ fontSize: "0.75rem", padding: "0.25rem 0.75rem" }}
                    >
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {tickets.length === 0 && (
                <tr>
                  <td colSpan={9}>
                    <div className="eg-empty">
                      <h3 className="eg-empty-title">No hall tickets found</h3>
                      <p className="eg-empty-desc">
                        There are no hall tickets matching your current filters.
                      </p>
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
              className="eg-btn disabled:opacity-30"
            >
              Previous
            </button>
            <span className="eg-pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
