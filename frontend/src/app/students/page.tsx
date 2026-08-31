"use client";

import { useEffect, useState } from "react";

interface Student {
  id: number;
  usn: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: Student[];
  page: number;
  page_size: number;
  total: number;
}

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function StudentsPage() {
  const [students, setStudents] = useState<Student[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editStudent, setEditStudent] = useState<Student | null>(null);
  const [formUsn, setFormUsn] = useState("");
  const [formName, setFormName] = useState("");
  const [error, setError] = useState("");

  const fetchStudents = async () => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (search) params.set("search", search);
    if (showInactive) params.set("include_inactive", "true");

    const res = await fetch(`${API}/api/v1/students?${params}`);
    const data: ListResponse = await res.json();
    setStudents(data.items);
    setTotal(data.total);
  };

  useEffect(() => {
    fetchStudents();
  }, [page, search, showInactive]);

  const handleCreate = async () => {
    setError("");
    const res = await fetch(`${API}/api/v1/students`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usn: formUsn, name: formName }),
    });
    if (res.ok) {
      setShowForm(false);
      setFormUsn("");
      setFormName("");
      fetchStudents();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to create student");
    }
  };

  const handleUpdate = async () => {
    if (!editStudent) return;
    setError("");
    const res = await fetch(`${API}/api/v1/students/${editStudent.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usn: formUsn, name: formName }),
    });
    if (res.ok) {
      setEditStudent(null);
      setFormUsn("");
      setFormName("");
      fetchStudents();
    } else {
      const err = await res.json();
      setError(err.detail || "Failed to update student");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this student?")) return;
    await fetch(`${API}/api/v1/students/${id}`, { method: "DELETE" });
    fetchStudents();
  };

  const openEdit = (s: Student) => {
    setEditStudent(s);
    setFormUsn(s.usn);
    setFormName(s.name);
    setShowForm(true);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="min-h-screen bg-[#050505] text-white p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold uppercase tracking-wider mb-2">
          Students
        </h1>
        <p className="text-[#999] mb-8">Manage student records</p>

        <div className="flex gap-4 mb-6">
          <input
            type="text"
            placeholder="Search by USN or name..."
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
              setEditStudent(null);
              setFormUsn("");
              setFormName("");
              setShowForm(true);
            }}
            className="bg-gradient-to-r from-cyan-500 to-pink-500 px-4 py-2 rounded-lg font-medium hover:opacity-90"
          >
            + Add Student
          </button>
        </div>

        {showForm && (
          <div className="bg-[#111] border border-white/10 rounded-lg p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4">
              {editStudent ? "Edit Student" : "New Student"}
            </h2>
            {error && (
              <p className="text-pink-400 text-sm mb-4">{error}</p>
            )}
            <div className="flex gap-4">
              <input
                type="text"
                placeholder="USN"
                value={formUsn}
                onChange={(e) => setFormUsn(e.target.value)}
                className="flex-1 bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                placeholder="Name"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="flex-1 bg-[#050505] border border-white/10 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-cyan-500"
              />
              <button
                onClick={editStudent ? handleUpdate : handleCreate}
                className="bg-gradient-to-r from-cyan-500 to-pink-500 px-6 py-2 rounded-lg font-medium hover:opacity-90"
              >
                {editStudent ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  setEditStudent(null);
                  setError("");
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
                <th className="px-6 py-3">USN</th>
                <th className="px-6 py-3">Name</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr
                  key={s.id}
                  className="border-b border-white/5 hover:bg-white/[0.02]"
                >
                  <td className="px-6 py-3 font-mono text-sm">{s.usn}</td>
                  <td className="px-6 py-3">{s.name}</td>
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
              {students.length === 0 && (
                <tr>
                  <td
                    colSpan={4}
                    className="px-6 py-8 text-center text-[#666]"
                  >
                    No students found
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
