import * as XLSX from "xlsx";

export interface ValidationError {
  row: number;
  column: string;
  message: string;
}

export interface ParsedSpreadsheet {
  headers: string[];
  rows: Record<string, unknown>[];
  rawRows: unknown[][];
}

export interface ValidationResult<T> {
  valid: T[];
  invalid: { row: Record<string, unknown>; errors: ValidationError[] }[];
  allRows: { row: Record<string, unknown>; errors: ValidationError[]; valid: boolean }[];
}

export function parseSpreadsheet(file: File): Promise<ParsedSpreadsheet> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target?.result as ArrayBuffer);
        const workbook = XLSX.read(data, { type: "array" });
        const sheetName = workbook.SheetNames[0];
        if (!sheetName) {
          reject(new Error("Spreadsheet contains no sheets"));
          return;
        }
        const sheet = workbook.Sheets[sheetName];
        const jsonData = XLSX.utils.sheet_to_json<Record<string, unknown>>(
          sheet,
          { defval: "" }
        );
        const rawRows = XLSX.utils.sheet_to_json<unknown[]>(sheet, {
          header: 1,
          defval: "",
        });
        const headers =
          jsonData.length > 0 ? Object.keys(jsonData[0]) : [];

        resolve({ headers, rows: jsonData, rawRows: rawRows.slice(1) });
      } catch {
        reject(new Error("Failed to parse spreadsheet file"));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read file"));
    reader.readAsArrayBuffer(file);
  });
}

export function generateTemplate(
  headers: string[],
  exampleRows: string[][],
  instructions: { column: string; description: string }[],
  sheetName = "Template"
): void {
  const wb = XLSX.utils.book_new();

  const templateData = [headers, ...exampleRows];
  const ws = XLSX.utils.aoa_to_sheet(templateData);

  ws["!cols"] = headers.map(() => ({ wch: 20 }));

  XLSX.utils.book_append_sheet(wb, ws, sheetName);

  const instructionData = [
    ["Column", "Description"],
    ...instructions.map((i) => [i.column, i.description]),
  ];
  const iws = XLSX.utils.aoa_to_sheet(instructionData);
  iws["!cols"] = [{ wch: 20 }, { wch: 60 }];
  XLSX.utils.book_append_sheet(wb, iws, "Instructions");

  XLSX.writeFile(wb, `${sheetName.toLowerCase().replace(/\s+/g, "_")}_template.xlsx`);
}

export function validateRows<T>(
  rows: Record<string, unknown>[],
  requiredColumns: string[],
  validateFn: (row: Record<string, unknown>, index: number) => ValidationError[],
  transformFn: (row: Record<string, unknown>) => T
): ValidationResult<T> {
  const valid: T[] = [];
  const invalid: { row: Record<string, unknown>; errors: ValidationError[] }[] =
    [];
  const allRows: {
    row: Record<string, unknown>;
    errors: ValidationError[];
    valid: boolean;
  }[] = [];

  rows.forEach((row, index) => {
    const errors: ValidationError[] = [];

    for (const col of requiredColumns) {
      const val = row[col];
      if (val === undefined || val === null || String(val).trim() === "") {
        errors.push({
          row: index + 1,
          column: col,
          message: `${col} is required`,
        });
      }
    }

    const customErrors = validateFn(row, index);
    errors.push(...customErrors);

    if (errors.length === 0) {
      valid.push(transformFn(row));
      allRows.push({ row, errors: [], valid: true });
    } else {
      invalid.push({ row, errors });
      allRows.push({ row, errors, valid: false });
    }
  });

  return { valid, invalid, allRows };
}

export function exportFailedRows(
  failedRows: { row: Record<string, unknown>; errors: ValidationError[] }[],
  headers: string[]
): void {
  if (failedRows.length === 0) return;

  const data = [
    [...headers, "Errors"],
    ...failedRows.map((f) => [
      ...headers.map((h) => String(f.row[h] ?? "")),
      f.errors.map((e) => `${e.column}: ${e.message}`).join("; "),
    ]),
  ];

  const ws = XLSX.utils.aoa_to_sheet(data);
  ws["!cols"] = [...headers.map(() => ({ wch: 20 })), { wch: 50 }];
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Failed Rows");
  XLSX.writeFile(wb, "failed_rows.xlsx");
}

export function sheetDateToString(val: unknown): string {
  if (typeof val === "number") {
    const d = new Date((val - 25569) * 86400 * 1000);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${dd}`;
  }
  return String(val ?? "").trim();
}

export function sheetTimeToString(val: unknown): string {
  if (typeof val === "number") {
    const totalMinutes = Math.round(val * 24 * 60);
    const h = Math.floor(totalMinutes / 60);
    const m = totalMinutes % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  }
  return String(val ?? "").trim();
}
