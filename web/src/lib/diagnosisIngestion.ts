import JSZip from "jszip";
import mammoth from "mammoth";
import TurndownService from "turndown";
import * as XLSX from "xlsx";

import { runParserS3 } from "@/app/api/ralph/parse/handler";
import { readBytesFromS3 } from "@/lib/aws/s3Utils";

import type { UploadFileRecord } from "./jobStore";
import type { DiagnosisDocumentRole, DiagnosisNormalizedDocument, DiagnosisSourceFormat } from "./diagnosisTypes";

const turndown = new TurndownService({
  headingStyle: "atx",
  bulletListMarker: "-",
  codeBlockStyle: "fenced",
});

type NormalizationInput = {
  file: Pick<UploadFileRecord, "fileId" | "originalName" | "contentType" | "s3Bucket" | "s3Key">;
  role: DiagnosisDocumentRole;
};

function getExt(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

function asFormat(filename: string): DiagnosisSourceFormat {
  const ext = getExt(filename);
  switch (ext) {
    case ".xlsx":
      return "xlsx";
    case ".xls":
      return "xls";
    case ".pdf":
      return "pdf";
    case ".docx":
      return "docx";
    case ".pptx":
      return "pptx";
    default:
      throw new Error("UNSUPPORTED_DIAGNOSIS_DOCUMENT");
  }
}

function normalizeWhitespace(value: string): string {
  return value.replace(/\r\n/g, "\n").trim();
}

function xmlUnescape(value: string): string {
  return value
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, "\"")
    .replace(/&#39;/g, "'");
}

function extractXmlText(xml: string): string[] {
  const matches = [...xml.matchAll(/<a:t[^>]*>([\s\S]*?)<\/a:t>/g)];
  return matches
    .map((match) => normalizeWhitespace(xmlUnescape(match[1] ?? "")))
    .filter(Boolean);
}

function buildExcelMarkdown(buffer: Buffer) {
  const workbook = XLSX.read(buffer, { type: "buffer" });
  const markdownSections: string[] = [];
  const plainTextSections: string[] = [];

  for (const sheetName of workbook.SheetNames) {
    const sheet = workbook.Sheets[sheetName];
    if (!sheet) continue;
    const csv = XLSX.utils.sheet_to_csv(sheet, { blankrows: false }).trim();
    if (!csv) continue;
    markdownSections.push(`# ${sheetName}\n\n\`\`\`csv\n${csv}\n\`\`\``);
    plainTextSections.push(`[시트: ${sheetName}]\n${csv}`);
  }

  return {
    markdown: markdownSections.join("\n\n"),
    plainText: plainTextSections.join("\n\n"),
    metadata: {
      sheetCount: workbook.SheetNames.length,
      sheetNames: workbook.SheetNames,
    },
  };
}

async function normalizeExcel(input: NormalizationInput): Promise<DiagnosisNormalizedDocument> {
  const buffer = await readBytesFromS3(input.file.s3Key, input.file.s3Bucket);
  const parsed = buildExcelMarkdown(buffer);
  return {
    role: input.role,
    sourceFormat: asFormat(input.file.originalName),
    markdown: parsed.markdown,
    plainText: parsed.plainText,
    warnings: [],
    metadata: parsed.metadata,
  };
}

async function normalizePdf(input: NormalizationInput): Promise<DiagnosisNormalizedDocument> {
  const parsed = await runParserS3(input.file.s3Key, input.file.s3Bucket, false);
  const text = normalizeWhitespace(typeof parsed["text"] === "string" ? parsed["text"] : "");
  return {
    role: input.role,
    sourceFormat: "pdf",
    markdown: text,
    plainText: text,
    warnings: Array.isArray(parsed["warnings"])
      ? parsed["warnings"].map((warning) => String(warning))
      : [],
    metadata: {
      pageCount: typeof parsed["pages"] === "number" ? parsed["pages"] : 0,
      method: typeof parsed["method"] === "string" ? parsed["method"] : "",
    },
  };
}

async function normalizeDocx(input: NormalizationInput): Promise<DiagnosisNormalizedDocument> {
  const buffer = await readBytesFromS3(input.file.s3Key, input.file.s3Bucket);
  const [htmlResult, textResult] = await Promise.all([
    mammoth.convertToHtml({ buffer }),
    mammoth.extractRawText({ buffer }),
  ]);
  return {
    role: input.role,
    sourceFormat: "docx",
    markdown: normalizeWhitespace(turndown.turndown(htmlResult.value)),
    plainText: normalizeWhitespace(textResult.value),
    warnings: (htmlResult.messages ?? []).map((message) => message.message).filter(Boolean),
    metadata: {},
  };
}

async function normalizePptx(input: NormalizationInput): Promise<DiagnosisNormalizedDocument> {
  const buffer = await readBytesFromS3(input.file.s3Key, input.file.s3Bucket);
  const zip = await JSZip.loadAsync(buffer);
  const slideFiles = Object.keys(zip.files)
    .filter((name) => /^ppt\/slides\/slide\d+\.xml$/.test(name))
    .sort((a, b) => {
      const aNum = Number(a.match(/slide(\d+)\.xml$/)?.[1] ?? "0");
      const bNum = Number(b.match(/slide(\d+)\.xml$/)?.[1] ?? "0");
      return aNum - bNum;
    });

  const markdownSections: string[] = [];
  const plainTextSections: string[] = [];

  for (const slideFile of slideFiles) {
    const slideIndex = Number(slideFile.match(/slide(\d+)\.xml$/)?.[1] ?? "0");
    const slideXml = await zip.file(slideFile)?.async("string");
    const notesXml = await zip.file(`ppt/notesSlides/notesSlide${slideIndex}.xml`)?.async("string");
    const slideLines = slideXml ? extractXmlText(slideXml) : [];
    const noteLines = notesXml ? extractXmlText(notesXml) : [];

    const markdownParts = [`## 슬라이드 ${slideIndex}`];
    if (slideLines.length > 0) {
      markdownParts.push("", ...slideLines.map((line) => `- ${line}`));
    }
    if (noteLines.length > 0) {
      markdownParts.push("", "### 발표 메모", "", ...noteLines.map((line) => `- ${line}`));
    }
    markdownSections.push(markdownParts.join("\n"));

    const plainParts = [`[슬라이드 ${slideIndex}]`, ...slideLines];
    if (noteLines.length > 0) {
      plainParts.push("[메모]", ...noteLines);
    }
    plainTextSections.push(plainParts.join("\n"));
  }

  return {
    role: input.role,
    sourceFormat: "pptx",
    markdown: markdownSections.join("\n\n"),
    plainText: plainTextSections.join("\n\n"),
    warnings: [],
    metadata: {
      slideCount: slideFiles.length,
    },
  };
}

export async function normalizeDiagnosisDocumentFromUpload(
  input: NormalizationInput,
): Promise<DiagnosisNormalizedDocument> {
  const format = asFormat(input.file.originalName);
  switch (format) {
    case "xlsx":
    case "xls":
      return await normalizeExcel(input);
    case "pdf":
      return await normalizePdf(input);
    case "docx":
      return await normalizeDocx(input);
    case "pptx":
      return await normalizePptx(input);
  }
}
