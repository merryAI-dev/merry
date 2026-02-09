"use client";

import * as React from "react";
import { ArrowRight, FileText, RefreshCw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Textarea } from "@/components/ui/Textarea";

type ReportSession = {
  sessionId: string;
  title: string;
  createdAt?: string;
};

type ReportMessage = {
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
  member?: string;
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

export default function ReportPage() {
  const [sessions, setSessions] = React.useState<ReportSession[]>([]);
  const [activeSessionId, setActiveSessionId] = React.useState<string>("");
  const [messages, setMessages] = React.useState<ReportMessage[]>([]);
  const [prompt, setPrompt] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const activeSessionIdRef = React.useRef("");

  React.useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  const loadSessions = React.useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ sessions: ReportSession[] }>("/api/report/sessions");
      const list = res.sessions || [];
      setSessions(list);
      if (!activeSessionIdRef.current) {
        const first = list[0]?.sessionId;
        if (first) setActiveSessionId(first);
        else {
          const created = await fetchJson<{ sessionId: string }>("/api/report/sessions", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ title: "투자심사 보고서" }),
          });
          const res2 = await fetchJson<{ sessions: ReportSession[] }>("/api/report/sessions");
          setSessions(res2.sessions || []);
          setActiveSessionId(created.sessionId);
        }
      }
    } catch {
      setError("세션을 불러오지 못했습니다. 환경변수/인증을 확인하세요.");
    } finally {
      setBusy(false);
    }
  }, []);

  const loadMessages = React.useCallback(async (sessionId: string) => {
    if (!sessionId) return;
    setError(null);
    try {
      const res = await fetchJson<{ messages: ReportMessage[] }>(`/api/report/${sessionId}/messages`);
      setMessages(res.messages || []);
    } catch {
      setError("메시지를 불러오지 못했습니다.");
    }
  }, []);

  React.useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  React.useEffect(() => {
    if (activeSessionId) loadMessages(activeSessionId);
  }, [activeSessionId, loadMessages]);

  async function newSession() {
    setBusy(true);
    setError(null);
    try {
      const created = await fetchJson<{ sessionId: string }>("/api/report/sessions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: "투자심사 보고서" }),
      });
      await loadSessions();
      setActiveSessionId(created.sessionId);
      setMessages([]);
      setPrompt("");
    } catch {
      setError("새 세션 생성에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function sendMessage(message: string) {
    const text = message.trim();
    if (!text || !activeSessionId || sending) return;

    setSending(true);
    setError(null);

    const optimisticUser: ReportMessage = {
      role: "user",
      content: text,
      createdAt: new Date().toISOString(),
    };
    const optimisticAssistant: ReportMessage = {
      role: "assistant",
      content: "",
      createdAt: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticUser, optimisticAssistant]);
    setPrompt("");

    try {
      const res = await fetch("/api/report/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ sessionId: activeSessionId, message: text }),
      });

      if (!res.ok) {
        const json = await res.json().catch(() => ({}));
        throw new Error(json?.error || "FAILED");
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("NO_STREAM");

      const decoder = new TextDecoder("utf-8");
      let acc = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        acc += chunk;
        setMessages((prev) => {
          const next = [...prev];
          const idx = next.findLastIndex((m) => m.role === "assistant");
          if (idx >= 0) next[idx] = { ...next[idx], content: acc };
          return next;
        });
      }

      // Sync from server (ensures persisted copy and metadata).
      await loadMessages(activeSessionId);
    } catch {
      setError("전송/생성에 실패했습니다. Bedrock/LLM 환경변수와 모델 접근 권한을 확인하세요.");
    } finally {
      setSending(false);
    }
  }

  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content.trim());

  async function saveLastAsDraft() {
    if (!lastAssistant?.content?.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const title = `투자심사 보고서 초안 · ${new Date().toISOString().slice(0, 10)}`;
      const res = await fetchJson<{ draftId: string }>("/api/drafts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, content: lastAssistant.content }),
      });
      window.location.href = `/drafts/${res.draftId}`;
    } catch {
      setError("드래프트 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">Investment Report</div>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <h1 className="font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
              투자심사 보고서
            </h1>
            <Badge tone="accent">스트리밍</Badge>
          </div>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            대화로 초안을 만들고, 마지막 답변을 드래프트로 저장해 커서식 리뷰로 이어갑니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={loadSessions} disabled={busy}>
            <RefreshCw className="h-4 w-4" />
            새로고침
          </Button>
          <Button variant="secondary" onClick={newSession} disabled={busy}>
            새 세션
          </Button>
          <Button variant="primary" onClick={saveLastAsDraft} disabled={busy || !lastAssistant}>
            <FileText className="h-4 w-4" />
            마지막 답변 드래프트로
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <Card variant="strong" className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
          <div className="text-sm font-semibold text-[color:var(--ink)]">세션</div>
          <div className="mt-1 text-sm text-[color:var(--muted)]">
              팀 히스토리는 AWS(DynamoDB)에 저장됩니다.
          </div>
        </div>
          <select
            className="h-11 max-w-[34rem] rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
            value={activeSessionId}
            onChange={(e) => setActiveSessionId(e.target.value)}
            disabled={busy}
          >
            {sessions.map((s) => (
              <option key={s.sessionId} value={s.sessionId}>
                {s.title} · {s.createdAt?.slice(0, 16).replace("T", " ") || s.sessionId}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-[1.65fr_1fr]">
        <Card variant="strong" className="p-0">
          <div className="border-b border-[color:var(--line)] px-5 py-4">
            <div className="text-sm font-semibold text-[color:var(--ink)]">대화</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              답변은 Markdown 초안 형태로 생성됩니다.
            </div>
          </div>

          <div className="max-h-[720px] space-y-3 overflow-auto px-5 py-5">
            {messages.length ? (
              messages.map((m, idx) => (
                <div
                  key={idx}
                  className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
                >
                  <div
                    className={
                      m.role === "user"
                        ? "max-w-[84%] rounded-2xl bg-[color:color-mix(in_oklab,var(--accent),white_82%)] px-4 py-3 text-sm text-[color:var(--ink)]"
                        : "max-w-[84%] rounded-2xl border border-[color:var(--line)] bg-white/75 px-4 py-3 text-sm text-[color:var(--ink)]"
                    }
                  >
                    <div className="whitespace-pre-wrap">{m.content}</div>
                    <div className="mt-2 text-[10px] text-black/40">
                      {m.role === "user" ? "you" : "merry"} ·{" "}
                      {m.createdAt?.slice(0, 16).replace("T", " ") || ""}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-2xl border border-[color:var(--line)] bg-white/60 p-4 text-sm text-[color:var(--muted)]">
                시작 프롬프트 예시를 눌러 대화를 시작하세요.
              </div>
            )}
          </div>

          <div className="border-t border-[color:var(--line)] px-5 py-4">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={() => sendMessage("시장규모/성장률 근거를 정리해줘. 근거가 없으면 필요한 자료를 질문해줘.")}
                disabled={!activeSessionId || sending}
              >
                시장규모 근거
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  sendMessage("인수인의견 스타일로 투자심사 보고서 초안 문단을 작성해줘. 부족한 정보는 질문해줘.")
                }
                disabled={!activeSessionId || sending}
              >
                인수인의견 초안
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  sendMessage("시장규모 근거 요약 + 투자심사 보고서 초안(인수인의견 스타일)을 한 번에 작성해줘. 부족한 정보는 질문해줘.")
                }
                disabled={!activeSessionId || sending}
              >
                근거+초안
              </Button>
              <Button
                variant="secondary"
                onClick={() =>
                  sendMessage("리스크 섹션을 더 날카롭게 써줘. 법무/재무/사업/시장 측면으로 나눠줘.")
                }
                disabled={!activeSessionId || sending}
              >
                리스크 강화
              </Button>
            </div>

            <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_auto]">
              <Textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="보고서 작성 관련 질문..."
                className="min-h-24"
                disabled={!activeSessionId || sending}
              />
              <Button
                variant="primary"
                onClick={() => sendMessage(prompt)}
                disabled={!activeSessionId || sending || !prompt.trim()}
              >
                {sending ? (
                  <>
                    <Sparkles className="h-4 w-4 animate-pulse" />
                    생성 중
                  </>
                ) : (
                  <>
                    전송 <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </Button>
            </div>
          </div>
        </Card>

        <Card variant="strong" className="p-5">
          <div className="text-sm font-semibold text-[color:var(--ink)]">추천 체크</div>
          <div className="mt-1 text-sm text-[color:var(--muted)]">
            이 화면은 아직 Python 도구(시장 근거 추출, DART 수집 등) 연결 전입니다.
            대신 대화 초안 생성과 드래프트 리뷰 흐름부터 고정합니다.
          </div>

          <div className="mt-4 space-y-2 text-sm text-[color:var(--muted)]">
            <div className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
              <div className="text-xs font-semibold text-[color:var(--ink)]">다음 연결</div>
              <div className="mt-2">
                - PDF/엑셀 업로드 → 근거 추출<br />
                - DART 인수인의견 데이터셋 검색<br />
                - 심화 의견(딥 옵피니언) 파이프라인<br />
                - 결과를 자동으로 드래프트 버전으로 저장
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
