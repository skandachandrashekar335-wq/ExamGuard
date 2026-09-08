"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import * as XLSX from "xlsx";
import AppShell from "@/components/AppShell";
import { apiRequest } from "@/lib/api";
import {
  parseSpreadsheet,
  validateRows,
  exportFailedRows,
  sheetDateToString,
  sheetTimeToString,
  type ValidationError,
} from "@/lib/spreadsheet";

const MAX_SUBJECTS = 200;
const MAX_EXAMS = 500;

const SUBJECT_HEADERS = ["Code", "Name", "Department", "Semester", "Credits"];
const SUBJECT_REQUIRED = ["Code", "Name", "Department", "Semester"];

const EXAM_HEADERS = [
  "Subject Code",
  "Exam Name",
  "Exam Date",
  "Start Time",
  "End Time",
  "Semester",
  "Department",
];
const EXAM_REQUIRED = [
  "Subject Code",
  "Exam Name",
  "Exam Date",
  "Start Time",
  "End Time",
  "Semester",
  "Department",
];

interface SubjectItem {
  code: string;
  name: string;
  department: string;
  semester: number;
  credits?: number;
}

interface ExamItem {
  subject_code: string;
  exam_name: string;
  exam_date: string;
  start_time: string;
  end_time: string;
  semester: number;
  department: string;
}

interface SubjectResult {
  code: string;
  department: string;
  status: string;
  error?: string;
}

interface ExamResult {
  subject_code: string;
  exam_name: string;
  status: string;
  error?: string;
}

interface ImportResponse {
  subject_total: number;
  subject_created: number;
  subject_skipped: number;
  subject_failed: number;
  exam_total: number;
  exam_created: number;
  exam_skipped: number;
  exam_failed: number;
  subject_results: SubjectResult[];
  exam_results: ExamResult[];
}

type Phase = "select" | "preview" | "submitting" | "result";

interface RowState {
  row: Record<string, unknown>;
  errors: ValidationError[];
  valid: boolean;
  type: "subject" | "exam";
}

export default function ImportSubjectsExamsPage() {
  const [phase, setPhase] = useState<Phase>("select");
  const [subjects, setSubjects] = useState<RowState[]>([]);
  const [exams, setExams] = useState<RowState[]>([]);
  const [parseError, setParseError] = useState("");
  const [response, setResponse] = useState<ImportResponse | null>(null);
  const [submitError, setSubmitError] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const [activeTab, setActiveTab] = useState<"subjects" | "exams">("subjects");

  const validSubjects = subjects.filter((r) => r.valid).length;
  const invalidSubjects = subjects.filter((r) => !r.valid).length;
  const validExams = exams.filter((r) => r.valid).length;
  const invalidExams = exams.filter((r) => !r.valid).length;

  const reset = useCallback(() => {
    setPhase("select");
    setSubjects([]);
    setExams([]);
    setParseError("");
    setResponse(null);
    setSubmitError("");
    setActiveTab("subjects");
    if (fileRef.current) fileRef.current.value = "";
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setParseError("");
    setSubjects([]);
    setExams([]);

    try {
      const { rows: data } = await parseSpreadsheet(file);

      if (data.length === 0) {
        setParseError("File contains no data rows");
        return;
      }

      const hasSubjectCols = SUBJECT_REQUIRED.every((c) =>
        Object.keys(data[0]).some((k) => k.trim().toLowerCase() === c.toLowerCase())
      );
      const hasExamCols = EXAM_REQUIRED.every((c) =>
        Object.keys(data[0]).some((k) => k.trim().toLowerCase() === c.toLowerCase())
      );

      if (!hasSubjectCols && !hasExamCols) {
        setParseError(
          "File must contain either subject columns (Code, Name, Department, Semester) or exam columns (Subject Code, Exam Name, Exam Date, Start Time, End Time, Semester, Department)"
        );
        return;
      }

      if (hasSubjectCols) {
        if (data.length > MAX_SUBJECTS) {
          setParseError(`Too many subject rows: ${data.length} (max ${MAX_SUBJECTS})`);
          return;
        }
        const result = validateRows<SubjectItem>(
          data,
          SUBJECT_REQUIRED,
          (row) => {
            const errors: ValidationError[] = [];
            const sem = Number(row["Semester"]);
            if (!Number.isInteger(sem) || sem < 1 || sem > 8) {
              errors.push({ row: 0, column: "Semester", message: "Semester must be an integer between 1 and 8" });
            }
            const credits = row["Credits"];
            if (credits !== undefined && credits !== "" && credits !== null) {
              const c = Number(credits);
              if (!Number.isInteger(c) || c <= 0) {
                errors.push({ row: 0, column: "Credits", message: "Credits must be a positive integer" });
              }
            }
            return errors;
          },
          (row) => ({
            code: String(row["Code"] ?? "").trim(),
            name: String(row["Name"] ?? "").trim(),
            department: String(row["Department"] ?? "").trim(),
            semester: Number(row["Semester"]),
            credits: row["Credits"] ? Number(row["Credits"]) : undefined,
          })
        );

        setSubjects(
          data.map((row, i) => {
            const found = result.allRows[i];
            return { row, errors: found?.errors ?? [], valid: found?.valid ?? true, type: "subject" as const };
          })
        );
      }

      if (hasExamCols) {
        if (data.length > MAX_EXAMS) {
          setParseError(`Too many exam rows: ${data.length} (max ${MAX_EXAMS})`);
          return;
        }
        const result = validateRows<ExamItem>(
          data,
          EXAM_REQUIRED,
          (row) => {
            const errors: ValidationError[] = [];
            const sem = Number(row["Semester"]);
            if (!Number.isInteger(sem) || sem < 1 || sem > 8) {
              errors.push({ row: 0, column: "Semester", message: "Semester must be an integer between 1 and 8" });
            }
            const dateStr = sheetDateToString(row["Exam Date"]);
            if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
              errors.push({ row: 0, column: "Exam Date", message: "Date must be in YYYY-MM-DD format" });
            }
            return errors;
          },
          (row) => ({
            subject_code: String(row["Subject Code"] ?? "").trim(),
            exam_name: String(row["Exam Name"] ?? "").trim(),
            exam_date: sheetDateToString(row["Exam Date"]),
            start_time: sheetTimeToString(row["Start Time"]),
            end_time: sheetTimeToString(row["End Time"]),
            semester: Number(row["Semester"]),
            department: String(row["Department"] ?? "").trim(),
          })
        );

        setExams(
          data.map((row, i) => {
            const found = result.allRows[i];
            return { row, errors: found?.errors ?? [], valid: found?.valid ?? true, type: "exam" as const };
          })
        );
      }

      if (hasSubjectCols && !hasExamCols) setActiveTab("subjects");
      else if (hasExamCols && !hasSubjectCols) setActiveTab("exams");
      else setActiveTab("subjects");

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
    setPhase("submitting");
    setSubmitError("");

    const validSubj: SubjectItem[] = subjects
      .filter((r) => r.valid)
      .map((r) => ({
        code: String(r.row["Code"] ?? "").trim(),
        name: String(r.row["Name"] ?? "").trim(),
        department: String(r.row["Department"] ?? "").trim(),
        semester: Number(r.row["Semester"]),
        credits: r.row["Credits"] ? Number(r.row["Credits"]) : undefined,
      }));

    const validExam: ExamItem[] = exams
      .filter((r) => r.valid)
      .map((r) => ({
        subject_code: String(r.row["Subject Code"] ?? "").trim(),
        exam_name: String(r.row["Exam Name"] ?? "").trim(),
        exam_date: sheetDateToString(r.row["Exam Date"]),
        start_time: sheetTimeToString(r.row["Start Time"]),
        end_time: sheetTimeToString(r.row["End Time"]),
        semester: Number(r.row["Semester"]),
        department: String(r.row["Department"] ?? "").trim(),
      }));

    if (validSubj.length === 0 && validExam.length === 0) {
      setSubmitError("No valid rows to import");
      setPhase("preview");
      return;
    }

    try {
      const body: Record<string, unknown> = {};
      if (validSubj.length > 0) body.subjects = validSubj;
      if (validExam.length > 0) body.exams = validExam;

      const data: ImportResponse = await apiRequest("/api/v1/import/subjects-exams", {
        method: "POST",
        body: JSON.stringify(body),
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

    const subjData = [
      SUBJECT_HEADERS,
      ["CS501", "Data Structures", "Computer Science", 3, 4],
      ["CS502", "Algorithms", "Computer Science", 4, 3],
    ];
    const wsSubj = XLSX.utils.aoa_to_sheet(subjData);
    wsSubj["!cols"] = SUBJECT_HEADERS.map(() => ({ wch: 20 }));
    XLSX.utils.book_append_sheet(wb, wsSubj, "Subjects");

    const examData = [
      EXAM_HEADERS,
      ["CS501", "Midterm Exam", "2026-10-15", "10:00", "12:00", 3, "Computer Science"],
    ];
    const wsExam = XLSX.utils.aoa_to_sheet(examData);
    wsExam["!cols"] = EXAM_HEADERS.map(() => ({ wch: 20 }));
    XLSX.utils.book_append_sheet(wb, wsExam, "Exams");

    const instructions = [
      ["Column", "Sheet", "Description"],
      ["Code", "Subjects", "Subject code, e.g. CS501 (required, max 20 chars)"],
      ["Name", "Subjects", "Subject name (required, max 255 chars)"],
      ["Department", "Both", "Department offering the subject (required, max 100 chars)"],
      ["Semester", "Both", "Semester number 1-8 (required)"],
      ["Credits", "Subjects", "Credit hours (optional, positive integer)"],
      ["Subject Code", "Exams", "Must match a Subject Code from the Subjects sheet"],
      ["Exam Name", "Exams", "Name of the exam (required)"],
      ["Exam Date", "Exams", "Date in YYYY-MM-DD format (required)"],
      ["Start Time", "Exams", "Time in HH:MM format (required)"],
      ["End Time", "Exams", "Time in HH:MM format (required)"],
    ];
    const wsInst = XLSX.utils.aoa_to_sheet(instructions);
    wsInst["!cols"] = [{ wch: 18 }, { wch: 12 }, { wch: 60 }];
    XLSX.utils.book_append_sheet(wb, wsInst, "Instructions");

    XLSX.writeFile(wb, "subjects_exams_template.xlsx");
  };

  const handleExportFailed = (type: "subjects" | "exams") => {
    const source = type === "subjects" ? subjects : exams;
    const headers = type === "subjects" ? SUBJECT_HEADERS : EXAM_HEADERS;
    const failed = source.filter((r) => !r.valid);
    exportFailedRows(
      failed.map((f) => ({ row: f.row, errors: f.errors })),
      headers
    );
  };

  const displayRows = activeTab === "subjects" ? subjects : exams;
  const displayValid = activeTab === "subjects" ? validSubjects : validExams;
  const displayInvalid = activeTab === "subjects" ? invalidSubjects : invalidExams;
  const displayHeaders = activeTab === "subjects" ? SUBJECT_HEADERS : EXAM_HEADERS;

  return (
    <AppShell>
      <div className="eg-page">
        <div className="eg-page-header">
          <div className="eg-breadcrumb">
            <Link href="/import">Import</Link> / Subjects & Exams
          </div>
          <h1 className="eg-page-title">Import Subjects &amp; Exams</h1>
          <p className="eg-page-desc">
            Upload an Excel or CSV file to bulk import subjects (max {MAX_SUBJECTS}) and exams (max {MAX_EXAMS})
          </p>
        </div>

        {phase === "select" && (
          <div>
            <div className="glass-surface glass p-6 mb-6">
              <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
                How to import
              </h2>
              <ol className="text-sm space-y-2 list-decimal list-inside" style={{ color: "var(--text-secondary)" }}>
                <li>Download the template file below</li>
                <li>Fill in the Subjects sheet and/or Exams sheet</li>
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
                  {subjects.length > 0 && (
                    <span style={{ color: "var(--text-secondary)" }}>
                      Subjects: <span className="eg-badge eg-badge-success">{validSubjects} valid</span>
                      {invalidSubjects > 0 && <span className="eg-badge eg-badge-danger">{invalidSubjects} errors</span>}
                    </span>
                  )}
                  {exams.length > 0 && (
                    <span style={{ color: "var(--text-secondary)" }}>
                      Exams: <span className="eg-badge eg-badge-success">{validExams} valid</span>
                      {invalidExams > 0 && <span className="eg-badge eg-badge-danger">{invalidExams} errors</span>}
                    </span>
                  )}
                </div>
                <div className="flex gap-3">
                  {displayInvalid > 0 && (
                    <button onClick={() => handleExportFailed(activeTab)} className="eg-btn">
                      Export Failed Rows
                    </button>
                  )}
                  <button onClick={reset} className="eg-btn">
                    Cancel
                  </button>
                  {validSubjects + validExams > 0 && (
                    <button onClick={handleSubmit} className="eg-btn eg-btn-primary">
                      Import All
                    </button>
                  )}
                </div>
              </div>
            </div>

            {subjects.length > 0 && exams.length > 0 && (
              <div className="flex gap-2 mb-6">
                <button
                  onClick={() => setActiveTab("subjects")}
                  className={`eg-btn ${activeTab === "subjects" ? "eg-btn-primary" : ""}`}
                >
                  Subjects ({subjects.length})
                </button>
                <button
                  onClick={() => setActiveTab("exams")}
                  className={`eg-btn ${activeTab === "exams" ? "eg-btn-primary" : ""}`}
                >
                  Exams ({exams.length})
                </button>
              </div>
            )}

            {displayInvalid > 0 && (
              <div className="mb-6">
                <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--danger)" }}>
                  Rows With Errors ({displayInvalid})
                </h2>
                <div className="eg-table-wrap" style={{ borderColor: "var(--danger-border)" }}>
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        {displayHeaders.map((h) => (<th key={h}>{h}</th>))}
                        <th>Errors</th>
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.filter((r) => !r.valid).map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-muted)" }}>{displayRows.indexOf(r) + 1}</td>
                          {displayHeaders.map((h) => (<td key={h} className="text-sm">{String(r.row[h] ?? "")}</td>))}
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

            {displayValid > 0 && (
              <div>
                <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--success)" }}>
                  Valid Rows ({displayValid})
                </h2>
                <div className="eg-table-wrap">
                  <table className="eg-table">
                    <thead>
                      <tr>
                        <th>Row</th>
                        {displayHeaders.map((h) => (<th key={h}>{h}</th>))}
                      </tr>
                    </thead>
                    <tbody>
                      {displayRows.filter((r) => r.valid).map((r, i) => (
                        <tr key={i}>
                          <td style={{ color: "var(--text-muted)" }}>{displayRows.indexOf(r) + 1}</td>
                          {displayHeaders.map((h) => (<td key={h} className="text-sm">{String(r.row[h] ?? "")}</td>))}
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
            <p style={{ color: "var(--text-secondary)" }}>Importing subjects and exams...</p>
          </div>
        )}

        {phase === "result" && response && (
          <div>
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Subjects</h2>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Total", value: response.subject_total, color: "var(--text-primary)" },
                  { label: "Created", value: response.subject_created, color: "var(--success)" },
                  { label: "Skipped", value: response.subject_skipped, color: "var(--warning)" },
                  { label: "Failed", value: response.subject_failed, color: "var(--danger)" },
                ].map((stat) => (
                  <div key={stat.label} className="glass-surface glass p-4 text-center">
                    <p className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</p>
                    <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="mb-6">
              <h2 className="text-lg font-semibold mb-3" style={{ color: "var(--text-primary)" }}>Exams</h2>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: "Total", value: response.exam_total, color: "var(--text-primary)" },
                  { label: "Created", value: response.exam_created, color: "var(--success)" },
                  { label: "Skipped", value: response.exam_skipped, color: "var(--warning)" },
                  { label: "Failed", value: response.exam_failed, color: "var(--danger)" },
                ].map((stat) => (
                  <div key={stat.label} className="glass-surface glass p-4 text-center">
                    <p className="text-2xl font-bold" style={{ color: stat.color }}>{stat.value}</p>
                    <p className="text-sm" style={{ color: "var(--text-secondary)" }}>{stat.label}</p>
                  </div>
                ))}
              </div>
            </div>
            {response.subject_results.length > 0 && (
              <div className="eg-table-wrap mb-6">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Department</th>
                      <th>Status</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.subject_results.map((r, i) => (
                      <tr key={i}>
                        <td className="font-mono text-sm">{r.code}</td>
                        <td className="text-sm" style={{ color: "var(--text-secondary)" }}>{r.department}</td>
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
            {response.exam_results.length > 0 && (
              <div className="eg-table-wrap mb-6">
                <table className="eg-table">
                  <thead>
                    <tr>
                      <th>Subject</th>
                      <th>Exam Name</th>
                      <th>Status</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.exam_results.map((r, i) => (
                      <tr key={i}>
                        <td className="font-mono text-sm">{r.subject_code}</td>
                        <td className="text-sm">{r.exam_name}</td>
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
