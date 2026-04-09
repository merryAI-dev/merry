import * as XLSX from "xlsx";
import { readBytesFromS3 } from "@/lib/aws/s3Utils";

export type ParsedExcel = {
  text: string;
  sheetCount: number;
};

export function parseExcelBuffer(buffer: Buffer): ParsedExcel {
  const workbook = XLSX.read(buffer, { type: "buffer" });
  const parts: string[] = [];
  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    if (!sheet) continue;
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false });
    if (!csv.trim()) continue;
    parts.push(`[시트: ${sheetName}]\n${csv}`);
  }

  return {
    text: parts.join("\n\n"),
    sheetCount: workbook.SheetNames.length,
  };
}

/** Parse an Excel file from S3 into sheet-by-sheet CSV text. */
export async function parseExcelFromS3(s3Key: string, s3Bucket: string): Promise<string> {
  let buffer: Buffer | null = await readBytesFromS3(s3Key, s3Bucket);
  const parsed = parseExcelBuffer(buffer);
  buffer = null; // allow GC of raw bytes
  return parsed.text;
}

export async function parseExcelFromS3Detailed(s3Key: string, s3Bucket: string): Promise<ParsedExcel> {
  let buffer: Buffer | null = await readBytesFromS3(s3Key, s3Bucket);
  const parsed = parseExcelBuffer(buffer);
  buffer = null; // allow GC of raw bytes
  return parsed;
}
