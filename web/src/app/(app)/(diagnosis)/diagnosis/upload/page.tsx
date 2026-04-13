/* eslint-disable @next/next/no-img-element */
"use client";

import * as React from "react";
import { Loader2, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/apiClient";

export default function DiagnosisUploadPage() {
  const router = useRouter();
  const [file, setFile] = React.useState<File | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function startDiagnosis() {
    if (!file) {
      setError("진단 시트를 먼저 선택하세요.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const presign = await apiFetch<{
        file: { fileId: string };
        upload: { url: string; headers: Record<string, string> };
      }>("/api/uploads/presign", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          filename: file.name,
          contentType: file.type || "application/vnd.ms-excel",
          sizeBytes: file.size,
        }),
      });

      const putRes = await fetch(presign.upload.url, {
        method: "PUT",
        headers: presign.upload.headers,
        body: file,
      });
      if (!putRes.ok) throw new Error("UPLOAD_FAILED");

      await apiFetch("/api/uploads/complete", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: presign.file.fileId }),
      });

      const started = await apiFetch<{ href: string }>("/api/diagnosis/uploads", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ fileId: presign.file.fileId, title: file.name.replace(/\.[^.]+$/, "") }),
      });

      router.push(started.href);
    } catch (err) {
      const message = err instanceof Error ? err.message : "FAILED";
      if (message === "UPLOAD_FAILED") {
        setError("S3 업로드에 실패했습니다. 잠시 후 다시 시도하세요.");
      } else {
        setError("현황진단 세션을 시작하지 못했습니다.");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto grid max-w-5xl gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
          <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">
            Upload
          </div>
          <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">현황진단 시트 업로드</h1>
          <p className="mt-4 max-w-2xl text-base leading-7 text-[#6C624D]">
            엑셀 시트를 업로드하면 진단 세션을 만들고 기존 diagnosis 엔진으로 바로 실행을 시작합니다.
          </p>

          <div className="mt-8 rounded-[28px] border border-dashed border-[#C9B789] bg-[#FFFCF5] p-6">
            <label className="grid gap-3" htmlFor="diagnosis-upload-input">
              <span className="text-sm font-semibold text-[#5E5137]">진단 시트 파일</span>
              <input
                id="diagnosis-upload-input"
                type="file"
                accept=".xlsx,.xls"
                disabled={busy}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                className="block w-full rounded-2xl border border-[#E2D6BA] bg-white px-4 py-4 text-sm text-[#231F16]"
              />
            </label>
            <p className="mt-3 text-sm text-[#7C6E55]">
              지원 형식: `.xlsx`, `.xls`
            </p>
            {file ? (
              <div className="mt-4 rounded-2xl bg-[#F7EED9] px-4 py-3 text-sm text-[#5E5137]">
                선택된 파일: <span className="font-semibold">{file.name}</span>
              </div>
            ) : null}
            {error ? (
              <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {error}
              </div>
            ) : null}
            <div className="mt-6">
              <Button onClick={startDiagnosis} disabled={busy || !file}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UploadCloud className="h-4 w-4" />}
                진단 시작
              </Button>
            </div>
          </div>
        </section>

        <aside className="rounded-[32px] border border-[#E2D6BA] bg-[#2D2418] p-8 text-[#FFF3D6] shadow-[0_20px_44px_rgba(45,36,24,0.24)]">
          <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#F3C96B]">
            Workflow
          </div>
          <ol className="mt-5 space-y-4 text-sm leading-6 text-[#E7D6B1]">
            <li>1. 시트를 업로드하고 업로드 완료를 확인합니다.</li>
            <li>2. diagnosis 전용 세션과 실행 메타데이터를 별도 테이블에 기록합니다.</li>
            <li>3. 기존 `diagnosis_analysis` 엔진으로 실행을 전달합니다.</li>
            <li>4. 세션 화면에서 상태와 산출물을 확인합니다.</li>
          </ol>
        </aside>
      </div>
    </div>
  );
}
