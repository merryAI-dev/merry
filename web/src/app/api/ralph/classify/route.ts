import { NextResponse } from "next/server";
import { z } from "zod";

import { getUploadFile } from "@/lib/jobStore";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const ClassifySchema = z.object({
  fileIds: z.array(z.string().min(6)).min(1).max(20),
});

// 파일명 → 문서 타입 매핑 (한국어 키워드, ralph/router.py 미러)
const FILENAME_HINTS: [string, string[]][] = [
  ["business_reg", ["사업자등록증", "사업자등록", "사업자_등록"]],
  ["financial_stmt", ["재무제표", "표준재무", "재무상태표", "손익계산서"]],
  ["shareholder", ["주주명부", "주주_명부", "주주현황"]],
  ["investment_review", ["투자검토", "투자_검토", "ir자료", "ir_자료"]],
  ["employee_list", ["임직원명부", "임직원_명부", "4대보험", "사업장가입자"]],
  ["startup_cert", ["창업기업확인서", "창업기업_확인서", "창업확인"]],
  ["certificate", ["중소기업확인서", "벤처기업확인서", "기업부설연구소", "확인서"]],
  ["articles", ["정관", "articles_of_incorporation"]],
  ["corp_registry", ["등기부등본", "등기사항", "법인등기"]],
];

// 지원하는 추출 가능 문서 타입
const SUPPORTED_TYPES = [
  { value: "business_reg", label: "사업자등록증" },
  { value: "financial_stmt", label: "재무제표" },
  { value: "shareholder", label: "주주명부" },
  { value: "investment_review", label: "투자검토자료" },
  { value: "employee_list", label: "임직원명부" },
  { value: "certificate", label: "인증서" },
  { value: "startup_cert", label: "창업기업확인서" },
  { value: "articles", label: "정관" },
];

function detectTypeFromFilename(filename: string): { type: string | null; confidence: number } {
  // NFC 정규화 (macOS NFD 한글 대응)
  const name = filename
    .normalize("NFC")
    .replace(/\.[^.]+$/, "")
    .replace(/[_\-]/g, " ")
    .toLowerCase();
  const nameNoSpace = name.replace(/\s/g, "");

  for (const [docType, keywords] of FILENAME_HINTS) {
    for (const kw of keywords) {
      const kwLower = kw.toLowerCase();
      const kwNoSpace = kwLower.replace(/[_ ]/g, "");
      if (name.includes(kwLower) || nameNoSpace.includes(kwNoSpace)) {
        return { type: docType, confidence: 0.9 };
      }
    }
  }
  return { type: null, confidence: 0 };
}

export async function POST(req: Request) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const body = ClassifySchema.parse(await req.json());

    const files: {
      fileId: string;
      filename: string;
      detectedType: string | null;
      confidence: number;
    }[] = [];

    for (const fileId of body.fileIds) {
      const file = await getUploadFile(ws.teamId, fileId);
      if (!file) continue;
      const { type, confidence } = detectTypeFromFilename(file.originalName);
      files.push({
        fileId,
        filename: file.originalName,
        detectedType: type,
        confidence,
      });
    }

    return NextResponse.json({
      ok: true,
      files,
      supportedTypes: SUPPORTED_TYPES,
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 400;
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status });
  }
}
