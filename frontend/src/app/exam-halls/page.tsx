"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";

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
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <Link href="/" className="eg-breadcrumb">
            ← Home
          </Link>
          <h1 className="eg-page-title">Exam Halls</h1>
          <p className="eg-page-desc">Manage exam hall records</p>
        </div>

        <div className="eg-filter-bar">
          <input
            type="text"
            placeholder="Search by building, room, or name..."
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            className="eg-input"
            style={{ flex: 1 }}
          />
          <label className="eg-label" style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: 0 }}>
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="eg-checkbox"
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
            + Add Hall
          </button>
        </div>

        {showForm && (
          <div className="glass-surface" style={{ borderRadius: "var(--radius-lg)", padding: "1.5rem", marginBottom: "1.5rem" }}>
            <h2 style={{ fontFamily: "var(--font-display)", fontSize: "1.125rem", fontWeight: 500, color: "var(--text-primary)", marginBottom: "1rem" }}>
              {editHall ? "Edit Hall" : "New Hall"}
            </h2>
            {error && (
              <p style={{ color: "var(--danger)", fontSize: "0.875rem", marginBottom: "1rem" }}>{error}</p>
            )}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "1rem" }}>
              <div>
                <label className="eg-label">Building</label>
                <input
                  type="text"
                  placeholder="Building"
                  value={form.building}
                  onChange={(e) =>
                    setForm({ ...form, building: e.target.value })
                  }
                  className="eg-input"
                />
              </div>
              <div>
                <label className="eg-label">Room Number</label>
                <input
                  type="text"
                  placeholder="Room Number"
                  value={form.room_number}
                  onChange={(e) =>
                    setForm({ ...form, room_number: e.target.value })
                  }
                  className="eg-input"
                />
              </div>
              <div>
                <label className="eg-label">Name (optional)</label>
                <input
                  type="text"
                  placeholder="Name (optional)"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="eg-input"
                />
              </div>
              <div>
                <label className="eg-label">Capacity</label>
                <input
                  type="number"
                  placeholder="Capacity"
                  value={form.capacity}
                  onChange={(e) =>
                    setForm({ ...form, capacity: e.target.value })
                  }
                  className="eg-input"
                />
              </div>
              <div>
                <label className="eg-label">Rows (optional)</label>
                <input
                  type="number"
                  placeholder="Rows (optional)"
                  value={form.rows}
                  onChange={(e) => setForm({ ...form, rows: e.target.value })}
                  className="eg-input"
                />
              </div>
              <div>
                <label className="eg-label">Columns (optional)</label>
                <input
                  type="number"
                  placeholder="Columns (optional)"
                  value={form.columns}
                  onChange={(e) =>
                    setForm({ ...form, columns: e.target.value })
                  }
                  className="eg-input"
                />
              </div>
            </div>
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "1.25rem" }}>
              <button
                onClick={handleSubmit}
                className="eg-btn eg-btn-primary"
              >
                {editHall ? "Update" : "Create"}
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
                <th>Building</th>
                <th>Room</th>
                <th>Name</th>
                <th>Capacity</th>
                <th>Grid</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {halls.map((h) => (
                <tr key={h.id}>
                  <td>{h.building}</td>
                  <td>{h.room_number}</td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {h.name || "—"}
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {h.capacity}
                  </td>
                  <td style={{ color: "var(--text-muted)" }}>
                    {h.rows && h.columns ? `${h.rows}x${h.columns}` : "—"}
                  </td>
                  <td>
                    <span
                      className={`eg-badge ${h.is_active ? "eg-badge-success" : "eg-badge-danger"}`}
                    >
                      {h.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      onClick={() => openEdit(h)}
                      className="eg-btn eg-btn-ghost"
                      style={{ fontSize: "0.8125rem", padding: "0.25rem 0.5rem" }}
                    >
                      Edit
                    </button>
                    {h.is_active && (
                      <button
                        onClick={() => handleDeactivate(h.id)}
                        className="eg-btn eg-btn-danger"
                        style={{ fontSize: "0.8125rem", padding: "0.25rem 0.5rem", marginLeft: "0.5rem" }}
                      >
                        Deactivate
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {halls.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "var(--text-muted)", padding: "3rem 1rem" }}>
                    No exam halls found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="eg-pagination" style={{ marginTop: "1.25rem" }}>
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="eg-btn"
              style={{ opacity: page === 1 ? 0.3 : 1, cursor: page === 1 ? "not-allowed" : "pointer" }}
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
              style={{ opacity: page >= totalPages ? 0.3 : 1, cursor: page >= totalPages ? "not-allowed" : "pointer" }}
            >
              Next
            </button>
          </div>
        )}
      </div>
    </AppShell>
  );
}
