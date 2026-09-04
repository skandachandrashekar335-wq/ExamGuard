"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listEntryVerifications,
  createEntryVerification,
  type EntryVerification,
  type EntryVerificationCreate,
  ApiError,
} from "@/lib/entry-verification-api";

const STATUS_CLASSES: Record<string, string> = {
  PENDING: "border-white/20 text-[var(--text-secondary)]",
  IN_PROGRESS: "border-white/30 text-white",
  GRANTED: "border-white/40 text-white",
  DENIED: "border-white/20 text-[var(--text-secondary)]",
  ESCALATED: "border-white/30 text-white",
};

const CHECK_CLASSES: Record<string, string> = {
  PENDING: "border-white/10 text-[var(--text-muted)]",
  PASSED: "border-white/40 text-white",
  FAILED: "border-white/20 text-[var(--text-secondary)]",
  SKIPPED: "border-white/10 text-[var(--text-muted)]",
};

export default function EntryVerificationsPage() {
  const [items, setItems] = useState<EntryVerification[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState("");
  const [entryPointFilter, setEntryPointFilter] = useState("");
  const [studentFilter, setStudentFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<EntryVerificationCreate>({
    student_id: 0,
    exam_registration_id: 0,
    entry_point_id: 0,
    camera_id: null,
    hall_ticket_id: null,
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listEntryVerifications({
        page,
        page_size: pageSize,
        status: statusFilter || undefined,
        entry_point_id: entryPointFilter || undefined,
        student_id: studentFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError("Failed to load entry verifications");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [page, statusFilter, entryPointFilter, studentFilter]);

  const totalPages = Math.ceil(total / pageSize);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormError("");
    setFormLoading(true);
    try {
      const created = await createEntryVerification({
        student_id: form.student_id,
        exam_registration_id: form.exam_registration_id,
        entry_point_id: form.entry_point_id,
        camera_id: form.camera_id || undefined,
        hall_ticket_id: form.hall_ticket_id || undefined,
      });
      window.location.href = `/entry-verifications/${created.id}`;
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("Failed to create entry verification");
      }
    } finally {
      setFormLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)] p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-2">
          <h1 className="eg-display text-3xl">
            Entry Verifications
          </h1>
          <button
            onClick={() => setShowForm(!showForm)}
            className="eg-btn px-4 py-2 text-sm"
          >
            {showForm ? "Cancel" : "+ New Entry Verification"}
          </button>
        </div>
        <p className="eg-body text-[var(--text-secondary)] mb-8">
          Examination entry verification records — hall ticket, identity, and seat checks
        </p>

        {showForm && (
          <form
            onSubmit={handleCreate}
            className="border border-white/10 bg-[var(--bg-raised)] p-6 mb-8"
          >
            <h2 className="eg-mono text-sm text-[var(--text-secondary)] mb-4">
              Create Entry Verification
            </h2>
            {formError && (
              <div className="border border-white/10 bg-[var(--bg-base)] p-3 mb-4">
                <span className="eg-mono text-sm text-red-400">{formError}</span>
              </div>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                  Student ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.student_id || ""}
                  onChange={(e) =>
                    setForm({ ...form, student_id: Number(e.target.value) })
                  }
                  className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                  Registration ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.exam_registration_id || ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      exam_registration_id: Number(e.target.value),
                    })
                  }
                  className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                  Entry Point ID *
                </label>
                <input
                  type="number"
                  required
                  value={form.entry_point_id || ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      entry_point_id: Number(e.target.value),
                    })
                  }
                  className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
                />
              </div>
              <div>
                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                  Camera ID
                </label>
                <input
                  type="number"
                  value={form.camera_id ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      camera_id: e.target.value ? Number(e.target.value) : null,
                    })
                  }
                  className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30"
                  placeholder="Optional"
                />
              </div>
              <div>
                <label className="block eg-mono-sm text-[var(--text-muted)] mb-1">
                  Hall Ticket ID
                </label>
                <input
                  type="number"
                  value={form.hall_ticket_id ?? ""}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      hall_ticket_id: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                  className="w-full bg-[var(--bg-base)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30"
                  placeholder="Optional"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={formLoading}
              className="eg-btn px-4 py-2 text-sm disabled:opacity-30"
            >
              {formLoading ? "Creating..." : "Create Entry Verification"}
            </button>
          </form>
        )}

        <div className="flex flex-wrap gap-3 mb-6">
          <input
            type="text"
            placeholder="Student ID..."
            value={studentFilter}
            onChange={(e) => {
              setStudentFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 w-36"
          />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white focus:outline-none focus:border-white/30"
          >
            <option value="">All statuses</option>
            <option value="PENDING">Pending</option>
            <option value="IN_PROGRESS">In Progress</option>
            <option value="GRANTED">Granted</option>
            <option value="DENIED">Denied</option>
            <option value="ESCALATED">Escalated</option>
          </select>
          <input
            type="text"
            placeholder="Entry point ID..."
            value={entryPointFilter}
            onChange={(e) => {
              setEntryPointFilter(e.target.value);
              setPage(1);
            }}
            className="bg-[var(--bg-raised)] border border-white/10 px-3 py-2 text-sm text-white placeholder:text-[var(--text-muted)] focus:outline-none focus:border-white/30 w-40"
          />
        </div>

        {error && (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-4 mb-6">
            <span className="eg-mono text-red-400">{error}</span>
          </div>
        )}

        {loading ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <span className="eg-mono text-[var(--text-muted)]">
              Loading entry verifications...
            </span>
          </div>
        ) : items.length === 0 ? (
          <div className="border border-white/10 bg-[var(--bg-raised)] p-12 text-center">
            <h3 className="eg-mono text-[var(--text-secondary)] mb-2">
              No entry verifications
            </h3>
            <p className="text-sm text-[var(--text-muted)]">
              No entry verification records have been created yet.
            </p>
          </div>
        ) : (
          <div className="border border-white/10 bg-[var(--bg-raised)] overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    ID
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Student
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Reg
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Entry Point
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Hall
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Ticket
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Identity
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Seat
                  </th>
                  <th className="px-4 py-3 text-left eg-mono-sm text-[var(--text-muted)]">
                    Created
                  </th>
                  <th className="px-4 py-3 text-right eg-mono-sm text-[var(--text-muted)]">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((ev) => (
                  <tr
                    key={ev.id}
                    className="border-b border-white/5 hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-sm">{ev.id}</td>
                    <td className="px-4 py-3 text-sm">#{ev.student_id}</td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{ev.exam_registration_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{ev.entry_point_id}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)]">
                      #{ev.exam_hall_id}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          STATUS_CLASSES[ev.status] ||
                          "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {ev.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          CHECK_CLASSES[ev.hall_ticket_check] ||
                          "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {ev.hall_ticket_check}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          CHECK_CLASSES[ev.identity_check] ||
                          "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {ev.identity_check}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-[10px] eg-mono border px-2 py-0.5 ${
                          CHECK_CLASSES[ev.seat_check] ||
                          "border-white/10 text-[var(--text-muted)]"
                        }`}
                      >
                        {ev.seat_check}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">
                      {new Date(ev.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/entry-verifications/${ev.id}`}
                        className="eg-mono-sm text-white hover:text-[var(--text-secondary)] transition-colors"
                      >
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Prev
            </button>
            <span className="eg-mono-sm text-[var(--text-muted)]">
              {page} / {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn px-3 py-1 disabled:opacity-30"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
