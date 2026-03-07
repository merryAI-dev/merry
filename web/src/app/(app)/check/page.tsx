"use client";

import * as React from "react";
import {
  CheckCircle2,
  Download,
  FileText,
  Loader2,
  Plus,
  RefreshCw,
  ScanSearch,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { useToast } from "@/components/ui/Toast";
import { apiFetch } from "@/lib/apiClient";

/* ─────────────────────────────────────────────
   Types
───────────────────────────────────────────── */

type UploadPhase = "queued" | "uploading" | "done" | "error";

type FileEntry = {
  localId: string;
  file: File;
  phase: UploadPhase;
  progress: number;    // 0–100
  fileId: string | null;
  errorMsg: string | null;
};

type FileAction =
  | { type: "ADD"; files: File[] }
  | { type: "REMOVE"; localId: string }
  | { type: "CLEAR" }
  | { type: "SET_PHASE"; localId: string; phase: UploadPhase }
  | { type: "SET_PROGRESS"; localId: string; progress: number }
  | { type: "SET_DONE"; localId: string; fileId: string }
  | { type: "SET_ERROR"; localId: string; error: string };

function fileReducer(state: FileEntry[], action: FileAction): FileEntry[] {
  switch (action.type) {
    case "ADD": {
      const incoming = action.files
        // PDF만, 중복 제거 (같은 이름 + 크기)
        .filter(
          (f) =>
            f.name.toLowerCase().endsWith(".pdf") &&
            !state.some((e) => e.file.name === f.name && e.file.size === f.size),
        )
        .map<FileEntry>((f) => ({
          localId: crypto.randomUUID(),
          file: f,
          phase: "queued",
          progress: 0,
          fileId: null,
          errorMsg: null,
        }));
      return [...state, ...incoming].slice(0, MAX_FILES);
    }
    case "REMOVE":
      return state.filter((e) => e.localId !== action.localId);
    case "CLEAR":
      return [];
    case "SET_PHASE":
      return state.map((e) =>
        e.localId === action.localId ? { ...e, phase: action.phase } : e,
      );
    case "SET_PROGRESS":
      return state.map((e) =>
        e.localId === action.localId ? { ...e, progress: action.progress } : e,
      );
    case "SET_DONE":
      return state.map((e) =>
        e.localId === action.localId
          ? { ...e, phase: "done", progress: 100, fileId: action.fileId }
          : e,
      );
    case "SET_ERROR":
      return state.map((e) =>
        e.localId === action.localId
          ? { ...e, phase: "error", errorMsg: action.error }
          : e,
      );
  }
}

type PagePhase =
  | "setup"       // 설정 중
  | "uploading"   // S3 업로드 중
  | "submitting"  // 잡 생성 중
  | "polling"     // 워커 처리 대기
  | "done"        // 완료
  | "failed";     // 오류

type JobArtifact = {
  artifactId: string;
  label: string;
  contentType: string;
};

type JobRecord = {
  jobId: string;
  status: "queued" | "running" | "succeeded" | "failed";
  error?: string;
  artifacts?: JobArtifact[];
  metrics?: Record<string, unknown>;
  // Fan-out fields
  fanout?: boolean;
  totalTasks?: number;
  processedCount?: number;
  failedCount?: number;
  fanoutStatus?: "splitting" | "running" | "assembling" | "succeeded" | "failed";
};

/* ─────────────────────────────────────────────
   Constants
───────────────────────────────────────────── */

const MAX_FILES = 1000;
const MAX_CONDITIONS = 6;
const POLL_INTERVAL_MS = 3000;

/* ─────────────────────────────────────────────
   Upload helper
───────────────────────────────────────────── */

const MAX_FILE_SIZE_MB = 100; // 100MB per file.
const PDF_MAGIC = "%PDF-";

async function validatePdf(file: File): Promise<string | null> {
  // 1. Size check.
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    return `파일 크기가 ${MAX_FILE_SIZE_MB}MB를 초과합니다 (${(file.size / 1024 / 1024).toFixed(1)}MB)`;
  }
  if (file.size === 0) {
    return "빈 파일입니다";
  }

  // 2. PDF magic header check.
  try {
    const header = await file.slice(0, 5).text();
    if (header !== PDF_MAGIC) {
      return "유효한 PDF 파일이 아닙니다 (헤더 불일치)";
    }
  } catch {
    return "파일을 읽을 수 없습니다";
  }

  // 3. Encrypted PDF detection (check for /Encrypt in first 4KB).
  try {
    const chunk = await file.slice(0, 4096).text();
    if (chunk.includes("/Encrypt")) {
      return "암호화된 PDF입니다. 암호를 해제한 후 다시 시도하세요";
    }
  } catch {
    // Best-effort: if we can't read, skip this check.
  }

  return null; // Valid.
}

async function uploadOneFile(
  entry: FileEntry,
  dispatch: React.Dispatch<FileAction>,
): Promise<string> {
  // Pre-validate PDF before uploading.
  const validationError = await validatePdf(entry.file);
  if (validationError) {
    throw new Error(validationError);
  }

  dispatch({ type: "SET_PHASE", localId: entry.localId, phase: "uploading" });

  // 1. 서버에서 S3 presigned URL 발급 (uploadSessionId로 중복 방지)
  const presignData = await apiFetch<{
    ok: boolean;
    file: { fileId: string };
    upload: { method: string; url: string; headers?: Record<string, string> };
    error?: string;
  }>("/api/uploads/presign", {
    method: "POST",
    body: JSON.stringify({
      filename: entry.file.name,
      contentType: entry.file.type || "application/pdf",
      sizeBytes: entry.file.size,
      uploadSessionId: entry.localId,
    }),
  });

  const fileId = presignData.file.fileId as string;
  const uploadMeta = presignData.upload as {
    method: string;
    url: string;
    headers?: Record<string, string>;
  };

  // 2. S3에 직접 PUT (progress tracking용 XHR)
  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) {
        // S3 업로드: 0–90%, complete 호출 후 100%
        dispatch({
          type: "SET_PROGRESS",
          localId: entry.localId,
          progress: Math.round((e.loaded / e.total) * 90),
        });
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`S3 응답 ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("네트워크 오류"));
    xhr.open(uploadMeta.method, uploadMeta.url);
    if (uploadMeta.headers) {
      Object.entries(uploadMeta.headers).forEach(([k, v]) =>
        xhr.setRequestHeader(k, v),
      );
    }
    xhr.send(entry.file);
  });

  // 3. 서버에 업로드 완료 알림
  await apiFetch<{ ok: boolean }>("/api/uploads/complete", {
    method: "POST",
    body: JSON.stringify({ fileId }),
  });

  dispatch({ type: "SET_DONE", localId: entry.localId, fileId });
  return fileId;
}

/* ─────────────────────────────────────────────
   Page Component
───────────────────────────────────────────── */

export default function CheckPage() {
  const { toast } = useToast();
  const [files, dispatch] = React.useReducer(fileReducer, []);
  const [conditions, setConditions] = React.useState<string[]>(["", "", ""]);
  const [phase, setPhase] = React.useState<PagePhase>("setup");
  const [jobId, setJobId] = React.useState<string | null>(null);
  const [job, setJob] = React.useState<JobRecord | null>(null);
  const [globalError, setGlobalError] = React.useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  /* ── Derived ── */
  const filledConditions = conditions.filter((c) => c.trim());
  const uploadedCount = files.filter((f) => f.phase === "done").length;
  const errorCount = files.filter((f) => f.phase === "error").length;
  const canStart =
    phase === "setup" && files.length > 0 && filledConditions.length > 0;
  const isLocked = phase !== "setup";

  /* ── File handlers ── */
  const addFiles = React.useCallback((incoming: FileList | File[]) => {
    dispatch({ type: "ADD", files: Array.from(incoming) });
  }, []);

  const handleDrop = React.useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      if (!isLocked) addFiles(e.dataTransfer.files);
    },
    [isLocked, addFiles],
  );

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) addFiles(e.target.files);
    e.target.value = "";
  };

  /* ── Condition handlers ── */
  const updateCondition = (i: number, val: string) =>
    setConditions((prev) => prev.map((c, idx) => (idx === i ? val : c)));

  const addCondition = () => {
    if (conditions.length < MAX_CONDITIONS)
      setConditions((p) => [...p, ""]);
  };

  const removeCondition = (i: number) =>
    setConditions((p) =>
      p.length > 1 ? p.filter((_, idx) => idx !== i) : [""],
    );

  /* ── Main handler: 업로드 → 잡 생성 ── */
  const handleStart = React.useCallback(async () => {
    if (!canStart) return;
    setGlobalError(null);
    setPhase("uploading");

    // 모든 파일 병렬 업로드
    const results = await Promise.allSettled(
      files.map((entry) => uploadOneFile(entry, dispatch)),
    );

    const fileIds: string[] = [];
    results.forEach((result, i) => {
      if (result.status === "fulfilled") {
        fileIds.push(result.value);
      } else {
        dispatch({
          type: "SET_ERROR",
          localId: files[i].localId,
          error:
            result.reason instanceof Error
              ? result.reason.message
              : "업로드 실패",
        });
      }
    });

    if (fileIds.length === 0) {
      setPhase("failed");
      setGlobalError("모든 파일 업로드에 실패했습니다.");
      return;
    }

    // 잡 생성
    setPhase("submitting");
    try {
      const data = await apiFetch<{ ok: boolean; jobId: string }>("/api/jobs", {
        method: "POST",
        body: JSON.stringify({
          jobType: "condition_check",
          fileIds,
          params: { conditions: filledConditions },
        }),
      });
      setJobId(data.jobId);
      setPhase("polling");
      toast(`조건 검사 시작 (파일 ${fileIds.length}개)`, "success");
    } catch (err) {
      setPhase("failed");
      const msg = err instanceof Error ? err.message : "잡 생성 중 오류가 발생했습니다.";
      setGlobalError(msg);
      toast(msg, "error", 6000);
    }
  }, [canStart, files, filledConditions, toast]);

  /* ── ETA tracking ── */
  const [eta, setEta] = React.useState<string | null>(null);
  const progressRef = React.useRef<{ startTime: number; startCount: number } | null>(null);

  /* ── Stream job status (SSE with auto-reconnect + polling fallback) ── */
  React.useEffect(() => {
    if (!jobId || phase !== "polling") return;

    let cancelled = false;
    let sseRetries = 0;
    const MAX_SSE_RETRIES = 3;
    let currentEs: EventSource | null = null;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    function handleJobData(data: {
      status?: string;
      fanout?: boolean;
      totalTasks?: number;
      processedCount?: number;
      failedCount?: number;
      fanoutStatus?: string;
      artifacts?: JobArtifact[];
      metrics?: Record<string, unknown>;
      error?: string | null;
    }) {
      if (data.error === "NOT_FOUND") return;

      const processed = data.processedCount ?? 0;
      const total = data.totalTasks ?? 0;

      // ETA calculation.
      if (total > 0 && processed > 0) {
        if (!progressRef.current || progressRef.current.startCount === 0) {
          progressRef.current = { startTime: Date.now(), startCount: processed };
        }
        const elapsed = (Date.now() - progressRef.current.startTime) / 1000;
        const completed = processed - progressRef.current.startCount;
        if (completed > 0 && elapsed > 2) {
          const rate = completed / elapsed; // tasks per second
          const remaining = total - processed;
          const etaSec = Math.ceil(remaining / rate);
          if (etaSec < 60) setEta(`약 ${etaSec}초`);
          else if (etaSec < 3600) setEta(`약 ${Math.ceil(etaSec / 60)}분`);
          else setEta(`약 ${Math.ceil(etaSec / 3600)}시간`);
        }
      }

      setJob((prev) => ({
        jobId: jobId!,
        status: (data.status as JobRecord["status"]) ?? prev?.status ?? "queued",
        fanout: data.fanout ?? prev?.fanout,
        totalTasks: data.totalTasks ?? prev?.totalTasks,
        processedCount: data.processedCount ?? prev?.processedCount,
        failedCount: data.failedCount ?? prev?.failedCount,
        fanoutStatus: data.fanoutStatus as JobRecord["fanoutStatus"],
        artifacts: data.artifacts ?? prev?.artifacts,
        metrics: data.metrics ?? prev?.metrics,
        error: data.error ?? prev?.error,
      }));

      if (data.status === "succeeded") {
        setEta(null);
        setPhase("done");
        toast("조건 검사가 완료되었습니다", "success");
      } else if (data.status === "failed") {
        setEta(null);
        setPhase("failed");
        const errMsg = data.error ?? "처리 중 오류가 발생했습니다.";
        setGlobalError(errMsg);
        toast(errMsg, "error", 6000);
      }
    }

    function connectSSE() {
      if (cancelled) return;
      const es = new EventSource(`/api/jobs/${jobId}/stream`);
      currentEs = es;
      let hasReceivedData = false;

      es.onmessage = (ev) => {
        if (cancelled) return;
        hasReceivedData = true;
        sseRetries = 0; // Reset retry count on successful message.
        try {
          handleJobData(JSON.parse(ev.data));
        } catch {
          // parse error, ignore
        }
      };

      es.onerror = () => {
        if (cancelled) return;
        es.close();
        currentEs = null;

        if (!hasReceivedData && sseRetries === 0) {
          // SSE never connected — fall back to polling.
          startPolling();
          return;
        }

        // Auto-reconnect with backoff.
        sseRetries++;
        if (sseRetries <= MAX_SSE_RETRIES) {
          const delay = Math.min(1000 * Math.pow(2, sseRetries - 1), 5000);
          reconnectTimer = setTimeout(connectSSE, delay);
        } else {
          // Exhausted retries — fall back to polling.
          startPolling();
        }
      };
    }

    function startPolling() {
      if (pollTimer || cancelled) return;
      const poll = async () => {
        if (cancelled) return;
        try {
          const res = await fetch(`/api/jobs/${jobId}`);
          const d = await res.json();
          if (!d.ok || cancelled) return;
          handleJobData(d.job);
        } catch {
          // ignore
        }
      };
      poll();
      pollTimer = setInterval(poll, POLL_INTERVAL_MS);
    }

    connectSSE();

    return () => {
      cancelled = true;
      currentEs?.close();
      if (pollTimer) clearInterval(pollTimer);
      if (reconnectTimer) clearTimeout(reconnectTimer);
      progressRef.current = null;
      setEta(null);
    };
  }, [jobId, phase]);

  /* ── Download artifact ── */
  const handleDownload = React.useCallback(
    async (artifactId: string, filename: string) => {
      if (!jobId) return;
      try {
        const res = await fetch(
          `/api/jobs/${jobId}/artifact?artifactId=${encodeURIComponent(artifactId)}`,
        );
        const data = await res.json();
        if (!data.ok) return;
        const a = document.createElement("a");
        a.href = data.url as string;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } catch {
        // ignore
      }
    },
    [jobId],
  );

  /* ── Retry failed tasks ── */
  const [retrying, setRetrying] = React.useState(false);

  const handleRetryFailed = React.useCallback(async () => {
    if (!jobId || retrying) return;
    setRetrying(true);
    try {
      // Bulk retry all failed tasks via single API call.
      const res = await fetch(`/api/jobs/${jobId}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "failed" }),
      });
      const data = await res.json();
      if (data.ok && (data.retriedCount ?? 0) > 0) {
        // Reset ETA tracking and switch back to polling.
        progressRef.current = null;
        setPhase("polling");
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  }, [jobId, retrying]);

  /* ── Reset ── */
  const handleRetry = () => {
    dispatch({ type: "CLEAR" });
    setPhase("setup");
    setJobId(null);
    setJob(null);
    setGlobalError(null);
    // 조건은 유지
  };

  const handleReset = () => {
    dispatch({ type: "CLEAR" });
    setConditions(["", "", ""]);
    setPhase("setup");
    setJobId(null);
    setJob(null);
    setGlobalError(null);
  };

  /* ── Render ── */
  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col gap-4 max-md:h-auto max-md:min-h-[calc(100vh-5rem)]">

      {/* Header */}
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-[#8B95A1]">
          RALPH
        </div>
        <h1 className="mt-0.5 text-2xl font-black tracking-tight text-[#191F28]">
          조건 검사
        </h1>
        <p className="mt-1 text-sm text-[#8B95A1]">
          PDF를 업로드하고 자연어 조건을 입력하면 Nova Pro가 각 조건의 충족 여부를 판단합니다.
          결과는 CSV로 다운로드할 수 있습니다.
        </p>
      </div>

      {/* Split Panel — stack on mobile, side-by-side on desktop */}
      <div className="flex min-h-0 flex-1 gap-4 max-md:flex-col">

        {/* ── Left: 파일 목록 ── */}
        <div
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-[#E5E8EB] bg-white max-md:min-h-[300px]"
          onDragOver={(e) => { if (!isLocked) e.preventDefault(); }}
          onDrop={handleDrop}
        >
          {/* Panel header */}
          <div className="flex items-center justify-between border-b border-[#E5E8EB] px-4 py-3">
            <span className="text-sm font-medium text-[#191F28]">
              문서 목록
              {files.length > 0 && (
                <span className="ml-2 text-xs text-[#8B95A1]">
                  {files.length}개
                  {uploadedCount > 0 && phase !== "setup" &&
                    ` · 업로드 완료 ${uploadedCount}개`}
                  {errorCount > 0 && (
                    <span className="text-[#DC2626]"> · 오류 {errorCount}개</span>
                  )}
                </span>
              )}
            </span>
            {!isLocked && (
              <label
                htmlFor="check-file-input"
                className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-[#F2F4F6] px-3 py-1.5 text-xs font-medium text-[#4E5968] transition-colors hover:bg-[#E5E8EB]"
              >
                <Upload className="h-3.5 w-3.5" />
                파일 추가
              </label>
            )}
          </div>

          {/* File list / drop zone */}
          <div className="min-h-0 flex-1 overflow-auto">
            {files.length === 0 ? (
              <label
                htmlFor="check-file-input"
                className={`flex h-full flex-col items-center justify-center gap-3 text-center ${
                  !isLocked ? "cursor-pointer" : ""
                }`}
              >
                <Upload className="h-10 w-10 text-[#D1D5DC]" />
                <div>
                  <p className="text-sm font-medium text-[#8B95A1]">
                    PDF를 여기에 놓거나 클릭하여 추가하세요
                  </p>
                  <p className="mt-0.5 text-xs text-[#B0B8C1]">
                    최대 {MAX_FILES}개 · PDF만 지원
                  </p>
                </div>
              </label>
            ) : (
              <div className="flex flex-col divide-y divide-[#F2F4F6]">
                {files.map((entry) => (
                  <div
                    key={entry.localId}
                    className="flex items-center gap-3 px-4 py-2.5"
                  >
                    {/* 상태 아이콘 */}
                    {entry.phase === "done" ? (
                      <CheckCircle2 className="h-4 w-4 shrink-0 text-[#16A34A]" />
                    ) : entry.phase === "error" ? (
                      <XCircle className="h-4 w-4 shrink-0 text-[#DC2626]" />
                    ) : entry.phase === "uploading" ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[#3182F6]" />
                    ) : (
                      <FileText className="h-4 w-4 shrink-0 text-[#B0B8C1]" />
                    )}

                    {/* 파일명 + 진행 바 / 오류 메시지 */}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-[#191F28]">
                        {entry.file.name}
                      </p>
                      {entry.phase === "uploading" && (
                        <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[#E5E8EB]">
                          <div
                            className="h-full bg-[#3182F6] transition-all duration-200"
                            style={{ width: `${entry.progress}%` }}
                          />
                        </div>
                      )}
                      {entry.phase === "error" && entry.errorMsg && (
                        <p className="mt-0.5 text-xs text-[#DC2626]">
                          {entry.errorMsg}
                        </p>
                      )}
                    </div>

                    {/* 파일 크기 */}
                    <span className="shrink-0 text-xs text-[#B0B8C1]">
                      {(entry.file.size / 1024 / 1024).toFixed(1)}MB
                    </span>

                    {/* 삭제 (setup 상태만) */}
                    {!isLocked && (
                      <button
                        onClick={() =>
                          dispatch({ type: "REMOVE", localId: entry.localId })
                        }
                        className="shrink-0 text-[#D1D5DC] transition-colors hover:text-[#DC2626]"
                        title="파일 제거"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Right: 조건 입력 + 상태 카드 ── */}
        <div className="flex w-[360px] shrink-0 flex-col gap-4 overflow-y-auto max-md:w-full">

          {/* 조건 입력 패널 */}
          <div className="rounded-2xl border border-[#E5E8EB] bg-white">
            <div className="border-b border-[#E5E8EB] px-4 py-3">
              <p className="text-sm font-medium text-[#191F28]">검사 조건</p>
              <p className="mt-0.5 text-xs text-[#8B95A1]">
                각 문서에 동일한 조건을 적용합니다
              </p>
            </div>
            <div className="flex flex-col gap-2 p-4">
              {conditions.map((cond, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 shrink-0 text-right text-xs font-medium text-[#B0B8C1]">
                    {i + 1}
                  </span>
                  <input
                    type="text"
                    value={cond}
                    onChange={(e) => updateCondition(i, e.target.value)}
                    disabled={isLocked}
                    placeholder="예: 창업 3년 미만인가?"
                    className="flex-1 rounded-lg border border-[#E5E8EB] px-3 py-2 text-sm text-[#191F28] placeholder-[#D1D5DC] focus:border-[#191F28] focus:outline-none disabled:cursor-not-allowed disabled:bg-[#F8F9FA] disabled:text-[#8B95A1]"
                  />
                  {!isLocked && (
                    <button
                      onClick={() => removeCondition(i)}
                      className="shrink-0 text-[#D1D5DC] transition-colors hover:text-[#DC2626]"
                      title="조건 삭제"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
              {!isLocked && conditions.length < MAX_CONDITIONS && (
                <button
                  onClick={addCondition}
                  className="mt-1 flex items-center gap-1.5 text-sm text-[#8B95A1] transition-colors hover:text-[#191F28]"
                >
                  <Plus className="h-4 w-4" />
                  조건 추가
                </button>
              )}
            </div>
          </div>

          {/* 상태 / 결과 카드 */}
          {phase !== "setup" && (
            <div className="rounded-2xl border border-[#E5E8EB] bg-white p-4" aria-live="polite" aria-atomic="true">

              {/* 업로드 / 잡 생성 중 */}
              {(phase === "uploading" || phase === "submitting") && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-[#3182F6]" />
                    <span className="text-sm font-medium text-[#191F28]">
                      {phase === "uploading" ? "파일 업로드 중…" : "잡 생성 중…"}
                    </span>
                  </div>
                  {phase === "uploading" && (
                    <p className="text-xs text-[#8B95A1]">
                      {uploadedCount} / {files.length}개 완료
                    </p>
                  )}
                </div>
              )}

              {/* 워커 처리 대기 */}
              {phase === "polling" && (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-[#3182F6]" />
                    <span className="text-sm font-medium text-[#191F28]">
                      {job?.fanoutStatus === "assembling"
                        ? "결과 취합 중…"
                        : job?.status === "running"
                          ? "Nova Pro 처리 중…"
                          : "대기 중…"}
                    </span>
                  </div>

                  {/* Fan-out progress bar */}
                  {job?.fanout && job.totalTasks != null && job.totalTasks > 0 && (
                    <div className="flex flex-col gap-1.5">
                      <div
                        className="h-2 w-full overflow-hidden rounded-full bg-[#E5E8EB]"
                        role="progressbar"
                        aria-valuenow={job.processedCount ?? 0}
                        aria-valuemin={0}
                        aria-valuemax={job.totalTasks}
                        aria-label="작업 진행률"
                      >
                        <div
                          className="h-full rounded-full bg-[#3182F6] transition-all duration-500"
                          style={{
                            width: `${Math.min(100, Math.round(((job.processedCount ?? 0) / job.totalTasks) * 100))}%`,
                          }}
                        />
                      </div>
                      <div className="flex items-center justify-between">
                        <p className="text-xs text-[#8B95A1]">
                          {job.processedCount ?? 0} / {job.totalTasks} 처리 완료
                          {(job.failedCount ?? 0) > 0 && (
                            <span className="text-[#DC2626]">
                              {" "}(실패 {job.failedCount}건)
                            </span>
                          )}
                        </p>
                        {eta && (
                          <p className="text-xs text-[#8B95A1]">
                            남은 시간: {eta}
                          </p>
                        )}
                      </div>
                      <p className="text-[10px] text-[#B0B8C1]">
                        {Math.round(((job.processedCount ?? 0) / job.totalTasks) * 100)}%
                      </p>
                    </div>
                  )}

                  {/* Non-fanout fallback */}
                  {!job?.fanout && (
                    <p className="text-xs text-[#8B95A1]">
                      파일 {files.length}개 · 조건 {filledConditions.length}개
                    </p>
                  )}

                  {jobId && (
                    <p className="font-mono text-[10px] text-[#B0B8C1]">
                      잡 ID: {jobId}
                    </p>
                  )}
                </div>
              )}

              {/* 완료 */}
              {phase === "done" && job && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-[#16A34A]" />
                    <span className="text-sm font-semibold text-[#191F28]">
                      처리 완료
                    </span>
                  </div>
                  {job.metrics && (
                    <p className="text-xs text-[#8B95A1]">
                      성공{" "}
                      <span className="font-medium text-[#191F28]">
                        {(job.metrics.success_count as number) ?? 0}개
                      </span>{" "}
                      · 오류{" "}
                      <span className="font-medium text-[#DC2626]">
                        {(job.metrics.failed_count as number) ?? 0}개
                      </span>{" "}
                      · 총 {(job.metrics.total as number) ?? 0}개
                    </p>
                  )}
                  <div className="flex flex-col gap-2">
                    {job.artifacts?.map((a) => {
                      const filename = a.artifactId.includes("csv")
                        ? "condition_check_results.csv"
                        : "condition_check_results.json";
                      return (
                        <button
                          key={a.artifactId}
                          onClick={() => handleDownload(a.artifactId, filename)}
                          className="flex items-center gap-2 rounded-xl bg-[#F2F4F6] px-3 py-2.5 text-sm font-medium text-[#191F28] transition-colors hover:bg-[#E5E8EB]"
                        >
                          <Download className="h-4 w-4 text-[#3182F6]" />
                          {a.label}
                        </button>
                      );
                    })}
                  </div>
                  {/* Retry failed tasks button */}
                  {(job.failedCount ?? 0) > 0 && (
                    <button
                      onClick={handleRetryFailed}
                      disabled={retrying}
                      className="flex items-center gap-2 rounded-xl border border-[#DC2626]/20 bg-[#FFF5F5] px-3 py-2.5 text-sm font-medium text-[#DC2626] transition-colors hover:bg-[#FFEAEA] disabled:opacity-50"
                    >
                      <RefreshCw className={`h-4 w-4 ${retrying ? "animate-spin" : ""}`} />
                      {retrying ? "재시도 중…" : `실패 ${job.failedCount}건 재시도`}
                    </button>
                  )}
                  <button
                    onClick={handleReset}
                    className="mt-1 text-left text-xs text-[#8B95A1] transition-colors hover:text-[#191F28]"
                  >
                    새 검사 시작 →
                  </button>
                </div>
              )}

              {/* 오류 */}
              {phase === "failed" && (
                <div className="flex flex-col gap-3">
                  <div className="flex items-center gap-2">
                    <XCircle className="h-5 w-5 text-[#DC2626]" />
                    <span className="text-sm font-semibold text-[#DC2626]">
                      오류 발생
                    </span>
                  </div>
                  {globalError && (
                    <p className="rounded-lg bg-[#FFF5F5] px-3 py-2 text-xs text-[#DC2626]">
                      {globalError}
                    </p>
                  )}
                  {errorCount > 0 && (
                    <p className="text-xs text-[#8B95A1]">
                      업로드 실패 파일 {errorCount}개가 있습니다.
                      파일을 확인 후 다시 시도하세요.
                    </p>
                  )}
                  <button
                    onClick={handleRetry}
                    className="flex items-center justify-center gap-2 rounded-xl bg-[#191F28] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[#2D3540]"
                  >
                    다시 시도
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Action bar */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-[#B0B8C1]">
          {files.length > 0 || filledConditions.length > 0
            ? `파일 ${files.length}개 · 조건 ${filledConditions.length}개`
            : "파일을 추가하고 조건을 입력하세요"}
        </p>
        <button
          onClick={handleStart}
          disabled={!canStart}
          className="flex items-center gap-2 rounded-xl bg-[#191F28] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[#2D3540] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ScanSearch className="h-4 w-4" />
          검사 시작
        </button>
      </div>

      {/* Hidden file input */}
      <input
        id="check-file-input"
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        multiple
        className="hidden"
        onChange={handleInputChange}
      />
    </div>
  );
}
