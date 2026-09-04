"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listEntryPoints,
  createEntryPoint,
  updateEntryPoint,
  deactivateEntryPoint,
  listExamHalls,
  type EntryPoint,
  type EntryPointCreate,
  type ExamHall,
  ApiError,
} from "@/lib/camera-api";

export default function EntryPointsPage() {
  const [entryPoints, setEntryPoints] = useState<EntryPoint[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [showForm, setShowForm] = useState(false);
  const [editEP, setEditEP] = useState<EntryPoint | null>(null);
  const [form, setForm] = useState<EntryPointCreate>({
    name: "",
    code: "",
  });
  const [formError, setFormError] = useState("");
  const [formLoading, setFormLoading] = useState(false);

  const [halls, setHalls] = useState<ExamHall[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  async function loadHalls() {
    try {
      const data = await listExamHalls({ page_size: 100, include_inactive: true });
      setHalls(data.items);
    } catch {
      // Non-critical
    }
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listEntryPoints({
        page,
        page_size: pageSize,
        search: search || undefined,
        include_inactive: showInactive,
      });
      setEntryPoints(data.items);
      setTotal(data.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load entry points");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, showInactive]);

  useEffect(() => {
    loadHalls();
  }, []);

  function hallLabel(id: number | null): string {
    if (!id) return "—";
    const h = halls.find((h) => h.id === id);
    return h ? `${h.building} ${h.room_number}` : `Hall #${id}`;
  }

  function openCreate() {
    setEditEP(null);
    setForm({ name: "", code: "" });
    setFormError("");
    setShowForm(true);
  }

  function openEdit(ep: EntryPoint) {
    setEditEP(ep);
    setForm({
      name: ep.name,
      code: ep.code,
      description: ep.description || "",
      location_detail: ep.location_detail || "",
      exam_hall_id: ep.exam_hall_id || undefined,
    });
    setFormError("");
    setShowForm(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormLoading(true);
    setFormError("");
    try {
      const payload: EntryPointCreate = {
        name: form.name,
        code: form.code,
      };
      if (form.description) payload.description = form.description;
      if (form.location_detail) payload.location_detail = form.location_detail;
      if (form.exam_hall_id) payload.exam_hall_id = form.exam_hall_id;

      if (editEP) {
        await updateEntryPoint(editEP.id, payload);
      } else {
        await createEntryPoint(payload);
      }
      setShowForm(false);
      load();
    } catch (e) {
      if (e instanceof ApiError) {
        setFormError(e.message);
      } else {
        setFormError("An unexpected error occurred");
      }
    } finally {
      setFormLoading(false);
    }
  }

  async function handleDeactivate(id: number) {
    try {
      await deactivateEntryPoint(id);
      setConfirmDelete(null);
      load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Failed to deactivate entry point"
      );
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <Link
          href="/dashboard"
          className="text-[#999] hover:text-white text-sm mb-6 inline-block"
        >
          &larr; BACK TO DASHBOARD
        </Link>

        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold uppercase tracking-wider">
              Entry Points
            </h1>
            <p className="text-[#999] mt-1">
              Manage examination entry gates and access points
            </p>
          </div>
          <button
            onClick={openCreate}
            className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
          >
            + Add Entry Point
          </button>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mb-6">
          <input
            type="text"
            placeholder="SEARCH ENTRY POINTS..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            className="flex-1 bg-[#111] border border-white/10 px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-white/30 font-mono text-sm uppercase"
          />
          <label className="flex items-center gap-2 text-sm text-[#999] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => {
                setShowInactive(e.target.checked);
                setPage(1);
              }}
              className="accent-white"
            />
            INCLUDE INACTIVE
          </label>
        </div>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-4 py-3 mb-6 font-mono text-sm">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center py-20 text-[#666] font-mono text-sm uppercase">
            Loading entry points...
          </div>
        ) : entryPoints.length === 0 ? (
          <div className="text-center py-20">
            <p className="text-[#666] font-mono text-sm uppercase mb-4">
              No entry points configured
            </p>
            <button
              onClick={openCreate}
              className="bg-white text-black px-4 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] transition-colors"
            >
              + Add Entry Point
            </button>
          </div>
        ) : (
          <>
            <div className="bg-[#111] border border-white/10 overflow-hidden">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-white/10 text-xs text-[#999] uppercase tracking-wider">
                    <th className="px-4 py-3 font-mono">Name</th>
                    <th className="px-4 py-3 font-mono">Code</th>
                    <th className="px-4 py-3 font-mono">Location</th>
                    <th className="px-4 py-3 font-mono">Hall</th>
                    <th className="px-4 py-3 font-mono">Active</th>
                    <th className="px-4 py-3 font-mono">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {entryPoints.map((ep) => (
                    <tr
                      key={ep.id}
                      className="border-b border-white/5 hover:bg-white/[0.02]"
                    >
                      <td className="px-4 py-3 text-sm">{ep.name}</td>
                      <td className="px-4 py-3 text-sm font-mono text-[#999]">
                        {ep.code}
                      </td>
                      <td className="px-4 py-3 text-sm text-[#999]">
                        {ep.location_detail || ep.description || "—"}
                      </td>
                      <td className="px-4 py-3 text-sm text-[#999]">
                        {hallLabel(ep.exam_hall_id)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-mono ${
                            ep.is_active ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {ep.is_active ? "YES" : "NO"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm space-x-3">
                        <button
                          onClick={() => openEdit(ep)}
                          className="text-[#999] hover:text-white text-xs font-mono uppercase"
                        >
                          Edit
                        </button>
                        {ep.is_active && (
                          <button
                            onClick={() => setConfirmDelete(ep.id)}
                            className="text-[#999] hover:text-red-400 text-xs font-mono uppercase"
                          >
                            Deactivate
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between mt-4">
              <p className="text-xs text-[#666] font-mono">
                {total} TOTAL &middot; PAGE {page} OF {totalPages || 1}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1}
                  className="border border-white/20 px-3 py-1 text-xs font-mono uppercase disabled:opacity-30 hover:bg-white/5"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="border border-white/20 px-3 py-1 text-xs font-mono uppercase disabled:opacity-30 hover:bg-white/5"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}

        {/* Create/Edit Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-lg max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/10">
                <h2 className="text-lg font-mono uppercase tracking-wider">
                  {editEP ? "Edit Entry Point" : "Add Entry Point"}
                </h2>
                <button
                  onClick={() => setShowForm(false)}
                  className="text-[#666] hover:text-white text-xl"
                >
                  &times;
                </button>
              </div>
              <form onSubmit={handleSubmit} className="p-6 space-y-4">
                {formError && (
                  <div className="bg-red-900/20 border border-red-500/30 text-red-400 px-3 py-2 text-sm font-mono">
                    {formError}
                  </div>
                )}
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.name}
                    onChange={(e) =>
                      setForm((f) => ({ ...f, name: e.target.value }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                    placeholder="e.g. Main Gate"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Code *
                  </label>
                  <input
                    type="text"
                    required
                    value={form.code}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        code: e.target.value.toUpperCase(),
                      }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-white/30"
                    placeholder="e.g. MAIN_GATE"
                  />
                </div>
                <div>
                  <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                    Description
                  </label>
                  <input
                    type="text"
                    value={form.description || ""}
                    onChange={(e) =>
                      setForm((f) => ({
                        ...f,
                        description: e.target.value || null,
                      }))
                    }
                    className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                    placeholder="Optional description"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Location Detail
                    </label>
                    <input
                      type="text"
                      value={form.location_detail || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          location_detail: e.target.value || null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                      placeholder="e.g. Ground floor, east wing"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-mono text-[#999] uppercase mb-1">
                      Exam Hall
                    </label>
                    <select
                      value={form.exam_hall_id || ""}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          exam_hall_id: e.target.value
                            ? Number(e.target.value)
                            : null,
                        }))
                      }
                      className="w-full bg-[#0A0A0A] border border-white/10 px-3 py-2 text-white text-sm focus:outline-none focus:border-white/30"
                    >
                      <option value="">None</option>
                      {halls.map((h) => (
                        <option key={h.id} value={h.id}>
                          {h.building} {h.room_number}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="flex gap-3 pt-2">
                  <button
                    type="submit"
                    disabled={formLoading}
                    className="bg-white text-black px-6 py-2 font-mono text-sm uppercase tracking-wider hover:bg-[#E5E5E5] disabled:opacity-50 transition-colors"
                  >
                    {formLoading
                      ? "SAVING..."
                      : editEP
                        ? "UPDATE ENTRY POINT"
                        : "CREATE ENTRY POINT"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowForm(false)}
                    className="border border-white/20 px-6 py-2 font-mono text-sm uppercase text-[#999] hover:bg-white/5"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Deactivate Confirmation */}
        {confirmDelete !== null && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
            <div className="bg-[#111] border border-white/10 w-full max-w-sm p-6">
              <h2 className="text-lg font-mono uppercase tracking-wider mb-4">
                Deactivate Entry Point
              </h2>
              <p className="text-sm text-[#999] mb-6">
                This will deactivate the entry point. It will no longer appear
                in active operations.
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => handleDeactivate(confirmDelete)}
                  className="bg-red-900/50 border border-red-500/30 text-red-400 px-4 py-2 font-mono text-sm uppercase hover:bg-red-900/80 transition-colors"
                >
                  Deactivate
                </button>
                <button
                  onClick={() => setConfirmDelete(null)}
                  className="border border-white/20 px-4 py-2 font-mono text-sm uppercase text-[#999] hover:bg-white/5"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
