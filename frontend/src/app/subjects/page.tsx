"use client";

import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";

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
    const params: Record<string, string | number> = { page, page_size: pageSize };
    if (search) params.search = search;
    if (showInactive) params.include_inactive = "true";

    const data = await apiRequest<ListResponse>(`/api/v1/subjects${qs(params)}`);
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
      ? `/api/v1/subjects/${editSubject.id}`
      : "/api/v1/subjects";
    const method = editSubject ? "PATCH" : "POST";

    try {
      await apiRequest(url, { method, body: JSON.stringify(body) });
      setShowForm(false);
      resetForm();
      fetchSubjects();
    } catch (err: any) {
      setError(err.message || "Failed to save subject");
    }
  };

  const handleDeactivate = async (id: number) => {
    if (!confirm("Deactivate this subject?")) return;
    await apiRequest(`/api/v1/subjects/${id}`, { method: "DELETE" });
    fetchSubjects();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div>
            <h1 className="eg-page-title">Subjects</h1>
            <p className="eg-page-desc">Manage subject records</p>
          </div>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search by code or name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="eg-input flex-1"
          />
          <label className="eg-label">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="accent-[var(--accent)]"
            />
            Show inactive
          </label>
          <button
            onClick={() => {
              resetForm();
              setShowForm(true);
            }}
            className="eg-btn eg-btn-primary"
          >
            + Add Subject
          </button>
        </div>

        {showForm && (
          <div className="glass-surface p-6 mb-6">
            <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
              {editSubject ? "Edit Subject" : "New Subject"}
            </h2>
            {error && (
              <p className="text-sm mb-4" style={{ color: "var(--danger)" }}>{error}</p>
            )}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <input
                type="text"
                placeholder="Code (e.g. CS501)"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="eg-input"
              />
              <input
                type="text"
                placeholder="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="eg-input"
              />
              <input
                type="text"
                placeholder="Department"
                value={form.department}
                onChange={(e) =>
                  setForm({ ...form, department: e.target.value })
                }
                className="eg-input"
              />
              <select
                value={form.semester}
                onChange={(e) =>
                  setForm({ ...form, semester: Number(e.target.value) })
                }
                className="eg-select"
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
                className="eg-input"
              />
            </div>
            <div className="flex gap-4 mt-4">
              <button
                onClick={handleSubmit}
                className="eg-btn eg-btn-primary"
              >
                {editSubject ? "Update" : "Create"}
              </button>
              <button
                onClick={() => {
                  setShowForm(false);
                  resetForm();
                }}
                className="eg-btn"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <div className="eg-table-wrap">
          <table className="eg-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Department</th>
                <th>Semester</th>
                <th>Credits</th>
                <th>Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {subjects.map((s) => (
                <tr key={s.id}>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{s.code}</td>
                  <td>{s.name}</td>
                  <td>{s.department}</td>
                  <td>{s.semester}</td>
                  <td>{s.credits ?? "—"}</td>
                  <td>
                    <span className={`eg-badge ${s.is_active ? "eg-badge-success" : "eg-badge-danger"}`}>
                      {s.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => openEdit(s)}
                      className="eg-btn eg-btn-sm text-xs mr-4"
                    >
                      Edit
                    </button>
                    {s.is_active && (
                      <button
                        onClick={() => handleDeactivate(s.id)}
                        className="eg-btn eg-btn-danger eg-btn-sm text-xs"
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {subjects.length === 0 && (
                <tr>
                  <td colSpan={7}>
                    <div className="eg-empty">
                      <p className="eg-empty-title">No subjects found</p>
                      <p className="eg-empty-desc">Try adjusting your search or filters</p>
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
              className="eg-btn"
            >
              Previous
            </button>
            <span className="eg-pagination-info">
              Page {page} of {totalPages} ({total} total)
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="eg-btn"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
