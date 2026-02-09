"use client";

import Link from "next/link";
import * as React from "react";
import { Plus } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";

type DraftSummary = {
  draftId: string;
  title: string;
  createdAt?: string;
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

export default function DraftsPage() {
  const [drafts, setDrafts] = React.useState<DraftSummary[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [title, setTitle] = React.useState("투자심사 보고서 초안");
  const [content, setContent] = React.useState(
    `# 투자심사 보고서\n\n## 1. 회사 개요\n- \n\n## 2. 시장/경쟁\n- \n\n## 3. 투자 포인트\n- \n\n## 4. 리스크\n- \n\n## 5. 조건/요청사항\n- \n`,
  );

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ drafts: DraftSummary[] }>("/api/drafts");
      setDrafts(res.drafts || []);
    } catch {
      setError("드래프트 목록을 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load();
  }, []);

  async function createDraft() {
    if (!title.trim() || !content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ draftId: string }>("/api/drafts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, content }),
      });
      await load();
      // Redirect to the newly created draft for immediate review.
      window.location.href = `/drafts/${res.draftId}`;
    } catch {
      setError("드래프트 생성에 실패했습니다.");
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="text-sm font-medium text-[color:var(--muted)]">
          Drafts & Reviews
        </div>
        <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
          드래프트
        </h1>
        <div className="mt-2 text-sm text-[color:var(--muted)]">
          문서 버전, 코멘트 스레드, 반영 히스토리를 저장합니다.
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.2fr_1fr]">
        <Card variant="strong" className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-[color:var(--ink)]">
                새 드래프트 만들기
              </div>
              <div className="mt-1 text-sm text-[color:var(--muted)]">
                초안을 만들고, 특정 문장에 코멘트를 남겨 반영합니다.
              </div>
            </div>
            <Button variant="primary" onClick={createDraft} disabled={busy}>
              <Plus className="h-4 w-4" />
              생성
            </Button>
          </div>

          <div className="mt-4 space-y-3">
            <label className="block">
              <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">
                제목
              </div>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="block">
              <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">
                내용 (Markdown)
              </div>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                className="min-h-[340px] font-mono"
              />
            </label>
          </div>
        </Card>

        <Card variant="strong" className="p-5">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-[color:var(--ink)]">
              최근 드래프트
            </div>
            <Button variant="ghost" onClick={load} disabled={busy}>
              새로고침
            </Button>
          </div>
          <div className="mt-4 space-y-2">
            {drafts.map((d) => (
              <Link
                key={d.draftId}
                href={`/drafts/${d.draftId}`}
                className="block rounded-2xl border border-[color:var(--line)] bg-white/70 p-4 hover:bg-white/90"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium text-[color:var(--ink)]">
                      {d.title}
                    </div>
                    <div className="mt-1 text-xs text-[color:var(--muted)]">
                      {d.createdAt?.slice(0, 16).replace("T", " ") || ""}
                    </div>
                  </div>
                  <Badge tone="accent">열기</Badge>
                </div>
              </Link>
            ))}
            {!drafts.length ? (
              <div className="text-sm text-[color:var(--muted)]">
                아직 드래프트가 없습니다.
              </div>
            ) : null}
          </div>
        </Card>
      </div>
    </div>
  );
}

