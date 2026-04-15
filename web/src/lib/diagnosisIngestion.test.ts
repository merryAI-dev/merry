import { Buffer } from "node:buffer";

import * as XLSX from "xlsx";
import JSZip from "jszip";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  readBytesFromS3Mock,
  runParserS3Mock,
  mammothConvertToHtmlMock,
  mammothExtractRawTextMock,
} = vi.hoisted(() => ({
  readBytesFromS3Mock: vi.fn(),
  runParserS3Mock: vi.fn(),
  mammothConvertToHtmlMock: vi.fn(),
  mammothExtractRawTextMock: vi.fn(),
}));

vi.mock("@/lib/aws/s3Utils", () => ({
  readBytesFromS3: readBytesFromS3Mock,
}));

vi.mock("@/app/api/ralph/parse/handler", () => ({
  runParserS3: runParserS3Mock,
}));

vi.mock("mammoth", () => ({
  default: {
    convertToHtml: mammothConvertToHtmlMock,
    extractRawText: mammothExtractRawTextMock,
  },
  convertToHtml: mammothConvertToHtmlMock,
  extractRawText: mammothExtractRawTextMock,
}));

import { normalizeDiagnosisDocumentFromUpload } from "./diagnosisIngestion";

async function buildMinimalPptxBuffer(): Promise<Buffer> {
  const zip = new JSZip();
  zip.file(
    "ppt/slides/slide1.xml",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
      xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:cSld>
        <p:spTree>
          <p:sp>
            <p:txBody>
              <a:p><a:r><a:t>시장 진입 전략</a:t></a:r></a:p>
              <a:p><a:r><a:t>해외 진출 준비</a:t></a:r></a:p>
            </p:txBody>
          </p:sp>
        </p:spTree>
      </p:cSld>
    </p:sld>`,
  );
  zip.file(
    "ppt/notesSlides/notesSlide1.xml",
    `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
    <p:notes xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
      xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
      <p:cSld>
        <p:spTree>
          <p:sp>
            <p:txBody>
              <a:p><a:r><a:t>대표 발표 메모</a:t></a:r></a:p>
            </p:txBody>
          </p:sp>
        </p:spTree>
      </p:cSld>
    </p:notes>`,
  );

  return await zip.generateAsync({ type: "nodebuffer" });
}

describe("normalizeDiagnosisDocumentFromUpload", () => {
  beforeEach(() => {
    readBytesFromS3Mock.mockReset();
    runParserS3Mock.mockReset();
    mammothConvertToHtmlMock.mockReset();
    mammothExtractRawTextMock.mockReset();
  });

  it("normalizes xlsx uploads into markdown and plain text", async () => {
    const workbook = XLSX.utils.book_new();
    const sheet = XLSX.utils.aoa_to_sheet([
      ["항목", "값"],
      ["회사명", "비비비당"],
    ]);
    XLSX.utils.book_append_sheet(workbook, sheet, "기업정보");
    readBytesFromS3Mock.mockResolvedValue(XLSX.write(workbook, { type: "buffer", bookType: "xlsx" }));

    const normalized = await normalizeDiagnosisDocumentFromUpload({
      file: {
        fileId: "file-1",
        originalName: "bbb.xlsx",
        contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        s3Bucket: "bucket",
        s3Key: "uploads/team/file-1.xlsx",
      },
      role: "primary",
    });

    expect(normalized.sourceFormat).toBe("xlsx");
    expect(normalized.markdown).toContain("# 기업정보");
    expect(normalized.plainText).toContain("[시트: 기업정보]");
    expect(normalized.metadata.sheetCount).toBe(1);
  });

  it("normalizes pdf uploads through the existing ralph parser", async () => {
    runParserS3Mock.mockResolvedValue({
      text: "PDF 본문",
      pages: 3,
      method: "pymupdf",
      warnings: ["low_confidence"],
    });

    const normalized = await normalizeDiagnosisDocumentFromUpload({
      file: {
        fileId: "file-2",
        originalName: "deck.pdf",
        contentType: "application/pdf",
        s3Bucket: "bucket",
        s3Key: "uploads/team/file-2.pdf",
      },
      role: "context",
    });

    expect(runParserS3Mock).toHaveBeenCalledWith("uploads/team/file-2.pdf", "bucket", false);
    expect(normalized.sourceFormat).toBe("pdf");
    expect(normalized.plainText).toContain("PDF 본문");
    expect(normalized.metadata.pageCount).toBe(3);
    expect(normalized.warnings).toContain("low_confidence");
  });

  it("normalizes docx uploads into markdown", async () => {
    readBytesFromS3Mock.mockResolvedValue(Buffer.from("docx-binary"));
    mammothConvertToHtmlMock.mockResolvedValue({ value: "<h1>회사 개요</h1><p>핵심 지표</p>", messages: [] });
    mammothExtractRawTextMock.mockResolvedValue({ value: "회사 개요\n핵심 지표" });

    const normalized = await normalizeDiagnosisDocumentFromUpload({
      file: {
        fileId: "file-3",
        originalName: "memo.docx",
        contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        s3Bucket: "bucket",
        s3Key: "uploads/team/file-3.docx",
      },
      role: "context",
    });

    expect(normalized.sourceFormat).toBe("docx");
    expect(normalized.markdown).toContain("# 회사 개요");
    expect(normalized.plainText).toContain("핵심 지표");
  });

  it("normalizes pptx uploads into slide-ordered markdown", async () => {
    readBytesFromS3Mock.mockResolvedValue(await buildMinimalPptxBuffer());

    const normalized = await normalizeDiagnosisDocumentFromUpload({
      file: {
        fileId: "file-4",
        originalName: "briefing.pptx",
        contentType: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        s3Bucket: "bucket",
        s3Key: "uploads/team/file-4.pptx",
      },
      role: "context",
    });

    expect(normalized.sourceFormat).toBe("pptx");
    expect(normalized.markdown).toContain("## 슬라이드 1");
    expect(normalized.markdown).toContain("시장 진입 전략");
    expect(normalized.markdown).toContain("발표 메모");
    expect(normalized.metadata.slideCount).toBe(1);
  });
});
