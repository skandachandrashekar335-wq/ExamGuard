"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import * as XLSX from "xlsx";
import AppShell from "@/components/AppShell";
import { apiRequest, qs } from "@/lib/api";
import {
  parseSpreadsheet,
  validateRows,
  exportFailedRows,
  type ValidationError,
} from "@/lib/spreadsheet";

const MAX_ASSIGNMENTS = 200;

const HEADERS = ["Registration ID", "Seat Number", "Row", "Column"];
const REQUIRED_COLUMNS = ["Registration ID", "Seat Number"];

interface HallOption {
  id: number;
  building: string;
  room_number: string;
  name: string | null;
  capacity: number;
}

interface SeatItem {
  exam_registration_id: number;
  seat_number: string;
  row_number?: number;
  column_number?: number;
}

interface AssignmentResult {
  exam_registration_id: number;
  seat_number: string;
  status: string;
  assignment_id?: number;
  error?: string;
}

interface AssignmentResponse {
  total: number;
  assigned: number;
  skipped: number;
  failed: number;
  results: AssignmentResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

interface RowState {
  row: Record<string, unknown>;
  errors: ValidationError[];
  valid: boolean;
}

export default function ImportSeatAssignmentsPage() {
  const [halls, setHalls] = useState<HallOption[]>([]);
  const [selectedHallId, setSelectedHallId] = useState<number | null>(null);
  const [phase, setPhase] = useState<Phase>("select");
  const [rows, setRows] = useState<RowState[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<AssignmentResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const validCount = rows.filter((r) => r.valid).length;
  const invalidCount = rows.filter((r) => !r.valid).length;

  useEffect(() => {
    apiRequest<{ items: HallOption[] }>(`/api/v1/exam-halls${qs({ page: "1", page_size: "100" })}`)
      .then((data) => setHalls(data.items || []))
      .catch(() => {});
  }, []);

  const reset = useCallback(() => {
    setPhase("select");
    setRows([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setParseError("");
    setRows([]);

    try {
      const { rows: data } = await parseSpreadsheet(file);

      if (data.length === 0) {
        setParseError("File contains no data rows");
        return;
      }

      if (data.length > MAX_ASSIGNMENTS) {
        setParseError(`File contains ${data.length} rows, maximum is ${MAX_ASSIGNMENTS}`);
        return;
      }

      const result = validateRows<SeatItem>(
        data,
        REQUIRED_COLUMNS,
        (row) => {
          const errors: ValidationError[] = [];
          const regId = Number(row["Registration ID"]);
          if (!Number.isInteger(regId) || regId <= 0) {
            errors.push({ row: 0, column: "Registration ID", message: "Registration ID must be a positive integer" });
          }
          const seatNum = String(row["Seat Number"] ?? "").trim();
          if (seatNum.length > 50) {
            errors.push({ row: 0, column: "Seat Number", message: "Seat Number must be 50 characters or fewer" });
          }
          const rowVal = row["Row"];
          if (rowVal !== undefined && rowVal !== "" && rowVal !== null) {
            const r = Number(rowVal);
            if (!Number.isInteger(r) || r <= 0) {
              errors.push({ row: 0, column: "Row", message: "Row must be a positive integer" });
            }
          }
          const colVal = row["Column"];
          if (colVal !== undefined && colVal !== "" && colVal !== null) {
            const c = Number(colVal);
            if (!Number.isInteger(c) || c <= 0) {
              errors.push({ row: 0, column: "Column", message: "Column must be a positive integer" });
            }
          }
          return errors;
        },
        (row) => ({
          exam_registration_id: Number(row["Registration ID"]),
          seat_number: String(row["Seat Number"] ?? "").trim(),
          row_number: row["Row"] ? Number(row["Row"]) : undefined,
          column_number: row["Column"] ? Number(row["Column"]) : undefined,
        })
      );

      setRows(
        data.map((row, i) => {
          const found = result.allRows[i];
          return { row, errors: found?.errors ?? [], valid: found?.valid ?? true };
        })
      );
      setPhase("preview");
    } catch (err) {
      setParseError(err instanceof Error ? err.message : "Failed to parse file");
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const handleSubmit = async () => {
    if (!selectedHallId) return;
    setPhase("submitting");
    setSubmitError("");

    const assignments: SeatItem[] = rows
      .filter((r) => r.valid)
      .map((r) => ({
        exam_registration_id: Number(r.row["Registration ID"]),
        seat_number: String(r.row["Seat Number"] ?? "").trim(),
        row_number: r.row["Row"] ? Number(r.row["Row"]) : undefined,
        column_number: r.row["Column"] ? Number(r.row["Column"]) : undefined,
      }));

    try {
      const data: AssignmentResponse = await apiRequest("/api/v1/import/seat-assignments", {
        method: "POST",
        body: JSON.stringify({ exam_hall_id: selectedHallId, assignments }),
      });

      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const handleDownloadTemplate = () => {
    const wb = XLSX.utils.book_new();
    const data = [
      HEADERS,
      [1, "A1", 1, 1],
      [2, "A2", 1, 2],
      [3, "B1", 2, 1],
    ];
    const ws = XLSX.utils.aoa_to_sheet(data);
    ws["!cols"] = HEADERS.map(() => ({ wch: 18 }));
    XLSX.utils.book_append_sheet(wb, ws, "Template");

    const instructions = [
      ["Column", "Description"],
      ["Registration ID", "Numeric registration ID from the system (required, positive integer)"],
      ["Seat Number", "Seat identifier, e.g. A1, B3 (required, max 50 chars)"],
      ["Row", "Seating row number (optional, positive integer)"],
      ["Column", "Seating column number (optional, positive integer)"],
    ];
    const iws = XLSX.utils.aoa_to_sheet(instructions);
    iws["!cols"] = [{ wch: 18 }, { wch: 60 }];
    XLSX.utils.book_append_sheet(wb, iws, "Instructions");

    XLSX.writeFile(wb, "seat_assignments_template.xlsx");
  };

  const handleExportFailed = () => {
    const failed = rows.filter((r) => !r.valid);
    exportFailedRows(
      failed.map((f) => ({ row: f.row, errors: f.errors })),
      HEADERS
    );
  };

  const selectedHall = halls.find((h) => h.id === selectedHallId);

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div className="eg-breadcrumb">
            <Link href="/import">Import</Link> / Seat Assignments
          </div>
          <h1 className="eg-page-title">Import Seat Assignments</h1>
          <p className="eg-page-desc">
            Bulk assign seats in an exam hall (max {MAX_ASSIGNMENTS} per batch)
          </p>
        </div>

        {phase === "select" && (
          <div>
            <div className="glass-surface glass p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                Select Exam Hall
              </h2>
              <select
                value={selectedHallId ?? ""}
                onChange={(e) => setSelectedHallId(e.target.value ? Number(e.target.value) : null)}
                className="eg-select w-full"
              >
                <option value="">Choose an exam hall...</option>
                {halls.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.building} — Room {h.room_number}
                    {h.name ? ` (${h.name})` : ""} — Cap: {h.capacity}
                  </option>
                ))}
              </select>
            </div>

            {selectedHallId && (
              <>
                <div className="glass-surface glass p-6 mb-6">
                  <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                    How to import
                  </h2>
                  <ol className="text-sm space-y-2 list-decimal list-inside" style={{ color: "var(--text-secondary)" }}>
                    <li>Download the template file using the button below</li>
                    <li>Fill in Registration ID and Seat Number for each assignment</li>
                    <li>Optionally add Row and Column numbers</li>
                    <li>Save as .xlsx or .csv and upload</li>
                    <li>Review the preview and click Import</li>
                  </ol>
                  <button
                    onClick={handleDownloadTemplate}
                    className="eg-btn mt-4"
                  >
                    Download Template
                  </button>
                </div>

                <div
                  onDrop={handleDrop}
                  onDragOver={(e) => e.preventDefault()}
                  className="glass-surface border-2 border-dashed p-16 text-center cursor-pointer transition-colors hover:border-[var(--accent)]/50"
                  style={{ borderColor: "var(--border)" }}
                  onClick={() => fileRef.current?.click()}
                >
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xlsx,.csv"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleFile(file);
                    }}
                  />
                  <p className="text-lg mb-2" style={{ color: "var(--text-secondary)" }}>
                    Drop an Excel or CSV file here
                  </p>
                  <p className="text-sm" style={{ color: "var(--text-muted)" }}>
                    Accepts .xlsx and .csv files
                  </p>
                </div>
              </>
            )}
          </div>
        )}

        {parseError && (
          <div className="bg-[var(--danger-bg)] border border-[var(--danger-border)] rounded-lg p-4 mb-6">
            <p className="text-[var(--danger)] text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && selectedHall && (
          <div>
            <div className="glass-surface glass p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex gap-6 text-sm">
                  <span style={{ color: "var(--text-secondary)" }}>
                    Hall: <span style={{ color: "var(--text-primary)" }}>{selectedHall.building} — Room {selectedHall.room_number}</span>
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>
                    <span style={{ color: "var(--text-primary)" }} className="font-medium">{rows.length}</span> total rows
                  </span>
                  {validCount > 0 && <span className="eg-badge eg-badge-success">{validCount} valid</span>}
                  {invalidCount > 0 && <span className="eg-badge eg-badge-danger">{invalidCount} with errors</span>}
                </div>
                <div className="flex gap-3">
                  {invalidCount > 0 && (
                    <button onClick={handleExportFailed} className="eg-btn">
                      Export Failed Rows
                    </button>
                  )}
                  <button onClick={reset} className="eg-btn">
                    Cancel
                  </button>
                  {validCount > 0 && (
                    <button onClick={handleSubmit} className="eg-btn eg-btn-primary">
                      Assign {validCount} Seat{validCount !== 1 ? "s" : ""}
                    </button>
                  )}
                </div>
              </div>
            </div>

            {invalidCount > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--danger)" }}>
                  Rows With Errors ({invalidCount})
                </h2>
                <div className="eg-table-wrap" style={{ borderColor: "var(--danger-border)" }}>
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Reg ID</th>
                        <th>Seat</th>
                        <th>Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.filter((r) => !r.valid).map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-muted)" }}>{rows.indexOf(r) + 1}</td>
                          <td className="font-mono text-sm">{String(r.row["Registration ID"] ?? "")}</td>
                          <td className="font-mono text-sm">{String(r.row["Seat Number"] ?? "")}</td>
                          <td className="text-sm" style={{ color: "var(--danger)" }}>
                            {r.errors.map((e) => e.message).join("; ")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {validCount > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--success)" }}>
                  Valid Rows ({validCount})
                </h2>
                <div className="eg-table-wrap">
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        <th>Reg ID</th>
                        <th>Seat</th>
                        <th>Row #</th>
                        <th>Col #</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.filter((r) => r.valid).map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-muted)" }}>{rows.indexOf(r) + 1}</td>
                          <td className="font-mono text-sm">{String(r.row["Registration ID"] ?? "")}</td>
                          <td className="font-mono text-sm">{String(r.row["Seat Number"] ?? "")}</td>
                          <td className="text-sm" style={{ color: "var(--text-secondary)" }}>{String(r.row["Row"] ?? "\u2014")}</td>
                          <td className="text-sm" style={{ color: "var(--text-secondary)" }}>{String(r.row["Column"] ?? "\u2014")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {phase === "submitting" && (
          <div className="text-center py-16">
            <div className="inline-block w-8 h-8 border-2 border-t-transparent rounded-full animate-spin mb-4" style={{ borderColor: "var(--accent)", borderTopColor: "transparent" }} />
            <p style={{ color: "var(--text-secondary)" }}>Assigning seats...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total", value: response.total, color: "var(--text-primary)" },
                { label: "Assigned", value: response.assigned, color: "var(--success)" },
                { label: "Skipped", value: response.skipped, color: "var(--warning)" },
                { label: "Failed", value: response.failed, color: "var(--danger)" },
              ].map((stat) => (
                <div key={stat.label} className="glass-surface glass p-4 text-center">
                  <p className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</p>
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{stat.label}</p>
                </div>
              ))}
            </div>

            {response.results.length > 0 && (
              <div className="eg-table-wrap mb-6">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>Registration ID</th>
                      <th>Seat</th>
                      <th>Status</th>
                      <th>Assignment ID</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr key={i}>
                        <td className="font-mono text-sm">{r.exam_registration_id}</td>
                        <td className="font-mono text-sm">{r.seat_number}</td>
                        <td>
                          <span
                            className={`eg-badge ${
                              r.status === "assigned"
                                ? "eg-badge-success"
                                : r.status === "skipped"
                                ? "eg-badge-warning"
                                : "eg-badge-danger"
                            }`}
                          >
                            {r.status}
                          </span>
                        </td>
                        <td className="text-sm" style={{ color: "var(--text-secondary)" }}>
                          {r.assignment_id ?? "\u2014"}
                        </td>
                        <td className="text-sm" style={{ color: "var(--text-secondary)" }}>
                          {r.error || "\u2014"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <button onClick={reset} className="eg-btn eg-btn-primary">
              Import Another Batch
            </button>
          </div>
        )}

        {submitError && (
          <div className="bg-[var(--danger-bg)] border border-[var(--danger-border)] rounded-lg p-4 mt-4">
            <p className="text-[var(--danger)] text-sm">{submitError}</p>
          </div>
        )}

        <div className="mt-8">
          <Link href="/import" className="eg-btn text-sm">
            &larr; Back to Import
          </Link>
        </div>
      </div>
    </AppShell>
  );
}
