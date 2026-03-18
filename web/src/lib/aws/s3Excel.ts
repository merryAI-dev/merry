import * as XLSX from "xlsx";
import { readBytesFromS3 } from "@/lib/aws/s3Utils";

/** Parse an Excel file from S3 into sheet-by-sheet CSV text. */
export async function parseExcelFromS3(s3Key: string, s3Bucket: string): Promise<string> {
  let buffer: Buffer | null = await readBytesFromS3(s3Key, s3Bucket);
  const workbook = XLSX.read(buffer, { type: "buffer" });
  buffer = null; // allow GC of raw bytes

  const parts: string[] = [];
  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    if (!sheet) continue;
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false });
    if (!csv.trim()) continue;
    parts.push(`[시트: ${sheetName}]\n${csv}`);
  }

  return parts.join("\n\n");
}
