"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import {
  parseSpreadsheet,
  generateTemplate,
  validateRows,
  exportFailedRows,
  type ValidationError,
} from "@/lib/spreadsheet";
const MAX_STUDENTS = 500;

const HEADERS = ["USN", "Name"];
const REQUIRED_COLUMNS = ["USN", "Name"];

interface StudentItem {
  usn: string;
  name: string;
}

interface ImportResult {
  usn: string;
  status: string;
  error?: string;
}

interface ImportResponse {
  total: number;
  created: number;
  skipped: number;
  failed: number;
  results: ImportResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

interface RowState {
  row: Record<string, unknown>;
  errors: ValidationError[];
  valid: boolean;
}

export default function ImportStudentsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [rows, setRows] = useState<RowState[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const validCount = rows.filter((r) => r.valid).length;
  const invalidCount = rows.filter((r) => !r.valid).length;

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

      if (data.length > MAX_STUDENTS) {
        setParseError(
          `File contains ${data.length} rows, maximum is ${MAX_STUDENTS}`
        );
        return;
      }

      const result = validateRows<StudentItem>(
        data,
        REQUIRED_COLUMNS,
        (row) => {
          const errors: ValidationError[] = [];
          const usn = String(row["USN"] ?? "").trim();
          if (usn.length > 20) {
            errors.push({
              row: 0,
              column: "USN",
              message: "USN must be 20 characters or fewer",
            });
          }
          const name = String(row["Name"] ?? "").trim();
          if (name.length > 255) {
            errors.push({
              row: 0,
              column: "Name",
              message: "Name must be 255 characters or fewer",
            });
          }
          return errors;
        },
        (row) => ({
          usn: String(row["USN"] ?? "").trim(),
          name: String(row["Name"] ?? "").trim(),
        })
      );

      const rowStates = data.map((row, i) => {
        const found = result.allRows[i];
        return found ?? { row, errors: [], valid: true };
      });

      setRows(rowStates);
      setPhase("preview");
    } catch (err) {
      setParseError(
        err instanceof Error ? err.message : "Failed to parse file"
      );
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
    setPhase("submitting");
    setSubmitError("");

    const validStudents: StudentItem[] = rows
      .filter((r) => r.valid)
      .map((r) => ({
        usn: String(r.row["USN"] ?? "").trim(),
        name: String(r.row["Name"] ?? "").trim(),
      }));

    try {
      const data: ImportResponse = await apiRequest("/api/v1/import/students", {
        method: "POST",
        body: JSON.stringify({ students: validStudents }),
      });

      setResponse(data);
      setPhase("result");
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Import failed");
      setPhase("preview");
    }
  };

  const handleDownloadTemplate = () => {
    generateTemplate(
      HEADERS,
      [["CS001", "John Doe"], ["CS002", "Jane Smith"]],
      [
        { column: "USN", description: "University Seat Number (required, max 20 characters)" },
        { column: "Name", description: "Full name of the student (required, max 255 characters)" },
      ],
      "Students"
    );
  };

  const handleExportFailed = () => {
    const failed = rows.filter((r) => !r.valid);
    exportFailedRows(
      failed.map((f) => ({ row: f.row, errors: f.errors })),
      HEADERS
    );
  };

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div className="eg-breadcrumb">
            <Link href="/import">Import</Link> / Students
          </div>
          <h1 className="eg-page-title">Import Students</h1>
          <p className="eg-page-desc">
            Upload an Excel or CSV file to bulk import student records (max {MAX_STUDENTS})
          </p>
        </div>

        {phase === "select" && (
          <div>
            <div className="glass-surface glass p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                How to import
              </h2>
              <ol className="text-sm space-y-2 list-decimal list-inside" style={{ color: "var(--text-secondary)" }}>
                <li>Download the template file using the button below</li>
                <li>Fill in the student data in Excel or Google Sheets</li>
                <li>Save as .xlsx or .csv and upload the file</li>
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
          </div>
        )}

        {parseError && (
          <div className="bg-[var(--danger-bg)] border border-[var(--danger-border)] rounded-lg p-4 mb-6">
            <p className="text-[var(--danger)] text-sm">{parseError}</p>
          </div>
        )}

        {phase === "preview" && (
          <div>
            <div className="glass-surface glass p-4 mb-6">
              <div className="flex items-center justify-between">
                <div className="flex gap-6 text-sm">
                  <span style={{ color: "var(--text-secondary)" }}>
                    <span style={{ color: "var(--text-primary)" }} className="font-medium">{rows.length}</span>{" "}
                    total rows
                  </span>
                  {validCount > 0 && (
                    <span className="eg-badge eg-badge-success">{validCount} valid</span>
                  )}
                  {invalidCount > 0 && (
                    <span className="eg-badge eg-badge-danger">{invalidCount} with errors</span>
                  )}
                </div>
                <div className="flex gap-3">
                  {invalidCount > 0 && (
                    <button
                      onClick={handleExportFailed}
                      className="eg-btn"
                    >
                      Export Failed Rows
                    </button>
                  )}
                  <button onClick={reset} className="eg-btn">
                    Cancel
                  </button>
                  {validCount > 0 && (
                    <button
                      onClick={handleSubmit}
                      className="eg-btn eg-btn-primary"
                    >
                      Import {validCount} Student{validCount !== 1 ? "s" : ""}
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
                        <th>USN</th>
                        <th>Name</th>
                        <th>Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows
                        .filter((r) => !r.valid)
                        .map((r, i) => (
                          <tr key={i}>
                            <td style={{ color: "var(--text-muted)" }}>{rows.indexOf(r) + 1}</td>
                            <td className="font-mono text-sm">{String(r.row["USN"] ?? "")}</td>
                            <td className="text-sm">{String(r.row["Name"] ?? "")}</td>
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
                        <th>USN</th>
                        <th>Name</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows
                        .filter((r) => r.valid)
                        .map((r, i) => (
                          <tr key={i}>
                            <td style={{ color: "var(--text-muted)" }}>{rows.indexOf(r) + 1}</td>
                            <td className="font-mono text-sm">{String(r.row["USN"] ?? "")}</td>
                            <td className="text-sm">{String(r.row["Name"] ?? "")}</td>
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
            <p style={{ color: "var(--text-secondary)" }}>Importing students...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="grid grid-cols-4 gap-4 mb-6">
              {[
                { label: "Total", value: response.total, color: "var(--text-primary)" },
                { label: "Created", value: response.created, color: "var(--success)" },
                { label: "Skipped", value: response.skipped, color: "var(--warning)" },
                { label: "Failed", value: response.failed, color: "var(--danger)" },
              ].map((stat) => (
                <div
                  key={stat.label}
                  className="glass-surface glass p-4 text-center"
                >
                  <p className="text-2xl font-bold" style={{ color: stat.color }}>
                    {stat.value}
                  </p>
                  <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{stat.label}</p>
                </div>
              ))}
            </div>

            {response.results.length > 0 && (
              <div className="eg-table-wrap mb-6">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>USN</th>
                      <th>Status</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.results.map((r, i) => (
                      <tr key={i}>
                        <td className="font-mono text-sm">{r.usn}</td>
                        <td>
                          <span
                            className={`eg-badge ${
                              r.status === "created"
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
