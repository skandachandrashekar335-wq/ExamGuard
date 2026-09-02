"use client";

import { useEffect, useState } from "react";

interface ExamHall {
  id: number;
  building: string;
  room_number: string;
  name: string | null;
  capacity: number;
  rows: number | null;
  columns: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: ExamHall[];
  page: number;
  page_size: number;
  total: number;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ExamHallsPage() {
  const [halls, setHalls] = useState<ExamHall[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editHall, setEditHall] = useState<ExamHall | null>(null);
  const [form, setForm] = useState({
    building: "",
    room_number: "",
    name: "",
    capacity: "",
    rows: "",
    columns: "",
  });
  const [error, setError] = useState("");

  const fetchHalls = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set("search", search);
    if (showInactive) params.set("include_inactive", "true");

    const res = await fetch(`${API}/api/v1/exam-halls?${params}`);
    const data: ListResponse = await res.json();
    setHalls(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchHalls();
  }, [page, search, showInactive]);

  const resetForm = () => {
    setForm({
      building: "",
      room_number: "",
      name: "",
      capacity: "",
      rows: "",
      columns: "",
    });
    setEditHall(null);
    setError("");
  };

  const openEdit = (h: ExamHall) => {
    setEditHall(h);
    setForm({
      building: h.building,
      room_number: h.room_number,
      name: h.name || "",
      capacity: h.capacity.toString(),
      rows: h.rows?.toString() || "",
      columns: h.columns?.toString() || "",
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    setError("");
    const body: Record<string, unknown> = {
      building: form.building,
      room_number: form.room_number,
      capacity: Number(form.capacity),
    };
    if (form.name) body.name = form.name;
    if (form.rows) body.rows = Number(form.rows);
    if (form.columns) body.columns = Number(form.columns);

    const url = editHall
      ? `${API}/api/v1/exam-halls/${editHall.id}`
      : `${API}/api/v1/exam-halls`;
    const method = editHall ? "PATCH" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      setShowForm(false);
      resetForm();
      fetchHalls();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to save hall");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this hall?")) return;
    await fetch(`${API}/api/v1/exam-halls/${id}`, { method: "DELETE" });
    fetchHalls();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Exam Halls
        </h1>
        <p className="text-[#999] mb-8">Manage exam hall records</p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by building, room, or name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="flex-1 bg-[#111] border border-white/10 rounded-lg px-4 py-2 text-white placeholder:text-[#666] focus:outline-none focus:border-cyan-500"
          />
          <label className="flex items-center gap-2 text-sm text-[#999]">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="accent-cyan-500"
            />
            Show inactive
          </label>
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="bg-gradient-to-r from-cyan-500 to-pink-500 px-4 py-2 rounded-lg font-medium hover:opacity-90"
          >
            + Add Hall
          </button>
        </div>

        {showForm && (
          <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">
              {editHall ? "Edit Hall" : "New Hall"}
            </h2>
            {error && (
              <p className="text-pink-400 text-sm mb-4">{error}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <input
                type="text"
                placeholder="Building"
                value={form.building}
                onChange={(e) =>
                  setForm({ ...form, building: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Room Number"
                value={form.room_number}
                onChange={(e) =>
                  setForm({ ...form, room_number: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Name (optional)"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="number"
                placeholder="Capacity"
                value={form.capacity}
                onChange={(e) =>
                  setForm({ ...form, capacity: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="number"
                placeholder="Rows (optional)"
                value={form.rows}
                onChange={(e) => setForm({ ...form, rows: e.target.value })}
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="number"
                placeholder="Columns (optional)"
                value={form.columns}
                onChange={(e) =>
                  setForm({ ...form, columns: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
                className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
              >
                {editHall ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                className="border border-white/20 px-4 py-2 rounded-lg hover:bg-white/5"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="bg-[#111] border border-white/10 rounded-lg overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-white/10 text-left text-sm text-[#999]">
                <th className="px-6 py-3">Building</th>
                <th className="px-6 py-3">Room</th>
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Capacity</th>
                <th className="px-6 py-3">Grid</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {halls.map((h) => (
                <tr
                  key={h.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 text-sm">{h.building}</td>
                  <td className="px-6 py-3 text-sm">{h.room_number}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {h.name || "—"}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {h.capacity}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {h.rows && h.columns ? `${h.rows}x${h.columns}` : "—"}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        h.is_active
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {h.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => openEdit(h)}
                      className="text-cyan-400 hover:text-cyan-300 text-sm mr-4"
                    >
                      Edit
                    </button>
                    {h.is_active && (
                      <button
                        onClick={() => handleDeactivate(h.id)}
                        className="text-pink-400 hover:text-pink-300 text-sm"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {halls.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No exam halls found
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
