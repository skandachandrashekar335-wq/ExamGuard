"use client";

import { useEffect, useState } from "react";

interface Subject {
  id: number;
  code: string;
  name: string;
  department: string;
  semester: number;
  credits: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: Subject[];
  page: number;
  page_size: number;
  total: number;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SubjectsPage() {
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editSubject, setEditSubject] = useState<Subject | null>(null);
  const [form, setForm] = useState({
    code: "",
    name: "",
    department: "",
    semester: 1,
    credits: "",
  });
  const [error, setError] = useState("");

  const fetchSubjects = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set("search", search);
    if (showInactive) params.set("include_inactive", "true");

    const res = await fetch(`${API}/api/v1/subjects?${params}`);
    const data: ListResponse = await res.json();
    setSubjects(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchSubjects();
  }, [page, search, showInactive]);

  const resetForm = () => {
    setForm({ code: "", name: "", department: "", semester: 1, credits: "" });
    setEditSubject(null);
    setError("");
  };

  const openEdit = (s: Subject) => {
    setEditSubject(s);
    setForm({
      code: s.code,
      name: s.name,
      department: s.department,
      semester: s.semester,
      credits: s.credits?.toString() || "",
    });
    setShowForm(true);
  };

  const handleSubmit = async () => {
    setError("");
    const body: Record<string, unknown> = {
      code: form.code,
      name: form.name,
      department: form.department,
      semester: Number(form.semester),
    };
    if (form.credits) body.credits = Number(form.credits);

    const url = editSubject
      ? `${API}/api/v1/subjects/${editSubject.id}`
      : `${API}/api/v1/subjects`;
    const method = editSubject ? "PATCH" : "POST";

    const res = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (res.ok) {
      setShowForm(false);
      resetForm();
      fetchSubjects();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to save subject");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this subject?")) return;
    await fetch(`${API}/api/v1/subjects/${id}`, { method: "DELETE" });
    fetchSubjects();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Subjects
        </h1>
        <p className="text-[#999] mb-8">Manage subject records</p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by code or name..."
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
            + Add Subject
          </button>
        </div>

        {showForm && (
          <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">
              {editSubject ? "Edit Subject" : "New Subject"}
            </h2>
            {error && (
              <p className="text-pink-400 text-sm mb-4">{error}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <input
                type="text"
                placeholder="Code (e.g. CS501)"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Department"
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <select
                value={form.semester}
                onChange={(e) =>
                  setForm({ ...form, semester: Number(e.target.value) })
                }
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
                  <option key={s} value={s}>
                    Semester {s}
                  </option>
                ))}
              </select>
              <input
                type="number"
                placeholder="Credits"
                value={form.credits}
                onChange={(e) => setForm({ ...form, credits: e.target.value })}
                className="bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
                className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
              >
                {editSubject ? "Update" : "Create"}
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
                <th className="px-6 py-3">Code</th>
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Department</th>
                <th className="px-6 py-3">Semester</th>
                <th className="px-6 py-3">Credits</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 font-mono text-sm">{s.code}</td>
                  <td className="px-6 py-3 text-sm">{s.name}</td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {s.department}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {s.semester}
                  </td>
                  <td className="px-6 py-3 text-sm text-[#999]">
                    {s.credits ?? "—"}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className={`text-xs px-2 py-1 rounded-full ${
                        s.is_active
                          ? "bg-emerald-500/20 text-emerald-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-right">
                    <button
                      onClick={() => openEdit(s)}
                      className="text-cyan-400 hover:text-cyan-300 text-sm mr-4"
                    >
                      Edit
                    </button>
                    {s.is_active && (
                      <button
                        onClick={() => handleDeactivate(s.id)}
                        className="text-pink-400 hover:text-pink-300 text-sm"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {subjects.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No subjects found
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
