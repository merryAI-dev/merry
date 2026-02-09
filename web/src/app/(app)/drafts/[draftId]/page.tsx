"use client";

import * as React from "react";
import { useParams } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, ChevronDown, Sparkles, X } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/cn";

type DraftVersion = {
  versionId: string;
  title: string;
  content: string;
  createdBy: string;
  createdAt: string;
};

type DraftComment = {
  commentId: string;
  versionId: string;
  kind: "수정" | "좋음" | "대안";
  status: "open" | "accepted" | "rejected";
  text: string;
  anchor: { start: number; end: number; quote: string; context?: string };
  threadId: string;
  parentId?: string;
  createdBy: string;
  createdAt: string;
  updatedAt?: string;
};

type DraftDetailResponse = {
  versions: DraftVersion[];
  comments: DraftComment[];
};

type DraftThread = {
  threadId: string;
  root: DraftComment;
  replies: DraftComment[];
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function badgeForStatus(status: DraftComment["status"]) {
  if (status === "accepted") return <Badge tone="success">반영</Badge>;
  if (status === "rejected") return <Badge tone="danger">거절</Badge>;
  return <Badge tone="neutral">오픈</Badge>;
}

function badgeForKind(kind: DraftComment["kind"]) {
  if (kind === "좋음") return <Badge tone="success">좋음</Badge>;
  if (kind === "대안") return <Badge tone="warn">대안</Badge>;
  return <Badge tone="accent">수정</Badge>;
}

function groupThreads(comments: DraftComment[]): DraftThread[] {
  const byThread: Record<string, { root?: DraftComment; replies: DraftComment[] }> = {};

  for (const c of comments) {
    const threadId = c.threadId || c.commentId;
    const slot = byThread[threadId] ?? (byThread[threadId] = { replies: [] });
    if (c.parentId) slot.replies.push(c);
    else if (!slot.root) slot.root = c;
  }

  const threads: DraftThread[] = [];
  for (const [threadId, slot] of Object.entries(byThread)) {
    const root = slot.root ?? slot.replies[0];
    if (!root) continue;
    const replies = slot.replies
      .filter((r) => r.commentId !== root.commentId)
      .sort((a, b) => (a.createdAt || "").localeCompare(b.createdAt || ""));
    threads.push({ threadId, root, replies });
  }

  threads.sort((a, b) => (a.root.createdAt || "").localeCompare(b.root.createdAt || ""));
  return threads;
}

function createRangeFromOffsets(root: HTMLElement, start: number, end: number): Range | null {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node: Text | null = walker.nextNode() as Text | null;
  let idx = 0;

  const range = document.createRange();
  let startSet = false;

  while (node) {
    const len = node.nodeValue?.length ?? 0;
    const nextIdx = idx + len;

    if (!startSet && start <= nextIdx) {
      range.setStart(node, Math.max(0, start - idx));
      startSet = true;
    }
    if (startSet && end <= nextIdx) {
      range.setEnd(node, Math.max(0, end - idx));
      return range;
    }

    idx = nextIdx;
    node = walker.nextNode() as Text | null;
  }

  return null;
}

function findClosestOccurrence(text: string, quote: string, hintStart: number): number | null {
  const q = quote.trim();
  if (!q) return null;

  // Search locally first (reduces collisions when the same phrase repeats).
  const windowSize = 8000;
  const from = Math.max(0, hintStart - windowSize);
  const to = Math.min(text.length, hintStart + windowSize + q.length);
  const windowText = text.slice(from, to);

  let best: number | null = null;
  let idx = windowText.indexOf(q);
  let guard = 0;
  while (idx !== -1) {
    const pos = from + idx;
    if (best == null || Math.abs(pos - hintStart) < Math.abs(best - hintStart)) best = pos;
    idx = windowText.indexOf(q, idx + 1);
    guard += 1;
    if (guard > 200) break;
  }
  if (best != null) return best;

  // Fallback: global scan (still guarded).
  best = null;
  idx = text.indexOf(q);
  guard = 0;
  while (idx !== -1) {
    if (best == null || Math.abs(idx - hintStart) < Math.abs(best - hintStart)) best = idx;
    idx = text.indexOf(q, idx + 1);
    guard += 1;
    if (guard > 400) break;
  }
  return best;
}

export default function DraftDetailPage() {
  const params = useParams<{ draftId: string }>();
  const draftId = params.draftId;

  const [versions, setVersions] = React.useState<DraftVersion[]>([]);
  const [comments, setComments] = React.useState<DraftComment[]>([]);
  const [activeVersionId, setActiveVersionId] = React.useState<string | null>(null);
  const [activeThreadId, setActiveThreadId] = React.useState<string | null>(null);
  const [activeCommentId, setActiveCommentId] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const [editMode, setEditMode] = React.useState(false);
  const [editTitle, setEditTitle] = React.useState("");
  const [editContent, setEditContent] = React.useState("");

  const scrollRef = React.useRef<HTMLDivElement | null>(null);
  const contentRef = React.useRef<HTMLDivElement | null>(null);
  const [commentDraft, setCommentDraft] = React.useState({
    open: false,
    kind: "수정" as DraftComment["kind"],
    text: "",
    anchor: null as DraftComment["anchor"] | null,
    x: 0,
    y: 0,
  });

  const [replyDraft, setReplyDraft] = React.useState({
    threadId: null as string | null,
    kind: "대안" as DraftComment["kind"],
    text: "",
  });

  const [highlightRects, setHighlightRects] = React.useState<
    Array<{ top: number; left: number; width: number; height: number }>
  >([]);

  async function load() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<DraftDetailResponse>(`/api/drafts/${draftId}`);
      setVersions(res.versions || []);
      setComments(res.comments || []);
      const latest = (res.versions || []).at(-1)?.versionId || null;
      setActiveVersionId((prev) => prev ?? latest);
    } catch {
      setError("드래프트를 불러오지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftId]);

  const activeVersion = versions.find((v) => v.versionId === activeVersionId) || versions.at(-1) || null;
  const versionComments = comments.filter((c) => c.versionId === (activeVersion?.versionId ?? ""));
  const threads = React.useMemo(() => groupThreads(versionComments), [versionComments]);

  React.useEffect(() => {
    if (!activeVersion) return;
    setEditTitle(activeVersion.title);
    setEditContent(activeVersion.content);
  }, [activeVersion?.versionId]); // eslint-disable-line react-hooks/exhaustive-deps

  React.useEffect(() => {
    setActiveCommentId(null);
    setActiveThreadId(null);
    setReplyDraft({ threadId: null, kind: "대안", text: "" });
  }, [activeVersion?.versionId]);

  // Highlight currently selected comment (activeCommentId) using overlay rects.
  React.useEffect(() => {
    const scrollEl = scrollRef.current;
    const contentEl = contentRef.current;
    if (!scrollEl || !contentEl) return;
    if (!activeCommentId) {
      setHighlightRects([]);
      return;
    }
    const comment = versionComments.find((c) => c.commentId === activeCommentId);
    if (!comment) {
      setHighlightRects([]);
      return;
    }
    const commentEl = comment;
    const rootText = contentEl.textContent || "";
    let start = commentEl.anchor.start;
    let end = commentEl.anchor.end;

    function recompute(autoscroll: boolean) {
      const scroll = scrollEl as HTMLDivElement;
      // If offsets drift (new version/edits), try to re-anchor using the original quote near hint offset.
      if (
        start < 0 ||
        end < start ||
        end > rootText.length ||
        rootText.slice(start, end) !== commentEl.anchor.quote
      ) {
        const pos = findClosestOccurrence(rootText, commentEl.anchor.quote, Math.max(0, start));
        if (pos != null) {
          start = pos;
          end = pos + commentEl.anchor.quote.length;
        }
      }

      const r = createRangeFromOffsets(contentEl as HTMLElement, start, end);
      if (!r) return setHighlightRects([]);
      const rootRect = scroll.getBoundingClientRect();
      const rects = Array.from(r.getClientRects()).map((cr) => ({
        top: cr.top - rootRect.top + scroll.scrollTop,
        left: cr.left - rootRect.left + scroll.scrollLeft,
        width: cr.width,
        height: cr.height,
      }));
      setHighlightRects(rects);

      if (autoscroll && rects.length) {
        scroll.scrollTo({ top: Math.max(0, rects[0].top - 120), behavior: "smooth" });
      }
    }

    recompute(true);
    const onResize = () => recompute(false);
    window.addEventListener("resize", onResize);
    scrollEl.addEventListener("scroll", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      scrollEl.removeEventListener("scroll", onResize);
    };
  }, [activeCommentId, activeVersion?.versionId, versionComments]);

  function onDocMouseUp() {
    const scrollEl = scrollRef.current;
    const contentEl = contentRef.current;
    if (!scrollEl || !contentEl) return;
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0) return;
    const range = sel.getRangeAt(0);
    if (!contentEl.contains(range.commonAncestorContainer)) return;
    const quote = range.toString().trim();
    if (!quote) return;

    // Compute offsets by measuring text length from root start to range boundaries.
    const pre = document.createRange();
    pre.setStart(contentEl, 0);
    pre.setEnd(range.startContainer, range.startOffset);
    const start = pre.toString().length;
    const end = start + quote.length;
    const rootText = contentEl.textContent || "";
    const contextStart = Math.max(0, start - 40);
    const contextEnd = Math.min(rootText.length, end + 40);
    const context = rootText.slice(contextStart, contextEnd);

    const rect = range.getBoundingClientRect();
    const rootRect = scrollEl.getBoundingClientRect();
    const x = rect.left - rootRect.left + scrollEl.scrollLeft;
    const y = rect.bottom - rootRect.top + scrollEl.scrollTop + 8;

    setCommentDraft({
      open: true,
      kind: "수정",
      text: "",
      anchor: { start, end, quote, context },
      x,
      y,
    });
  }

  async function submitComment() {
    if (!activeVersion) return;
    if (!commentDraft.anchor || !commentDraft.text.trim()) return;
    try {
      const res = await fetchJson<{ commentId: string; threadId: string }>(`/api/drafts/${draftId}/comment`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          versionId: activeVersion.versionId,
          kind: commentDraft.kind,
          text: commentDraft.text,
          anchor: commentDraft.anchor,
        }),
      });
      setCommentDraft((p) => ({ ...p, open: false, text: "", anchor: null }));
      setActiveThreadId(res.threadId);
      setActiveCommentId(res.commentId);
      await load();
    } catch {
      setError("코멘트 저장에 실패했습니다.");
    }
  }

  async function submitReply(thread: DraftThread) {
    if (!activeVersion) return;
    if (replyDraft.threadId !== thread.threadId) return;
    if (!replyDraft.text.trim()) return;
    try {
      await fetchJson(`/api/drafts/${draftId}/comment`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          versionId: activeVersion.versionId,
          kind: replyDraft.kind,
          text: replyDraft.text,
          anchor: thread.root.anchor,
          threadId: thread.threadId,
          parentId: thread.root.commentId,
        }),
      });
      setReplyDraft({ threadId: null, kind: "대안", text: "" });
      await load();
    } catch {
      setError("답글 저장에 실패했습니다.");
    }
  }

  async function setStatus(commentId: string, status: DraftComment["status"]) {
    try {
      await fetchJson(`/api/drafts/${draftId}/comment-status`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ commentId, status }),
      });
      await load();
    } catch {
      setError("상태 변경에 실패했습니다.");
    }
  }

  async function applyAccepted() {
    if (!activeVersion) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ versionId: string }>(`/api/drafts/${draftId}/apply`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ baseVersionId: activeVersion.versionId }),
      });
      await load();
      setActiveVersionId(res.versionId);
      setActiveCommentId(null);
      setEditMode(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      if (msg === "NO_ACCEPTED_COMMENTS") {
        setError("반영할 코멘트가 없습니다. 먼저 코멘트를 '반영'으로 바꿔주세요.");
      } else {
        setError("반영 생성에 실패했습니다.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function saveManualVersion() {
    if (!editTitle.trim() || !editContent.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ versionId: string }>(`/api/drafts/${draftId}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title: editTitle, content: editContent }),
      });
      await load();
      setActiveVersionId(res.versionId);
      setEditMode(false);
    } catch {
      setError("버전 저장에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">
            Draft Review
          </div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            드래프트 리뷰
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            텍스트를 드래그해 코멘트를 남기고, 반영/거절을 기록합니다.
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="secondary" onClick={() => setEditMode((v) => !v)}>
            {editMode ? "미리보기" : "직접 편집"}
            <ChevronDown className={cn("h-4 w-4 transition-transform", editMode && "rotate-180")} />
          </Button>
          <Button variant="primary" onClick={applyAccepted} disabled={busy || !activeVersion}>
            <Sparkles className={cn("h-4 w-4", busy && "animate-pulse")} />
            반영본 생성
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[1.55fr_1fr]">
        <Card variant="strong" className="relative p-0">
          <div className="flex items-center justify-between gap-3 border-b border-[color:var(--line)] px-5 py-4">
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium text-[color:var(--muted)]">버전</div>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <select
                  className="h-10 max-w-[28rem] rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                  value={activeVersion?.versionId || ""}
                  onChange={(e) => {
                    setActiveVersionId(e.target.value);
                    setActiveCommentId(null);
                  }}
                >
                  {versions.map((v) => (
                    <option key={v.versionId} value={v.versionId}>
                      {v.title} · {v.createdAt?.slice(0, 16).replace("T", " ")} · {v.createdBy || "멤버"}
                    </option>
                  ))}
                </select>
                <Badge tone="neutral">
                  {threads.length} 스레드 · {versionComments.length} 코멘트
                </Badge>
              </div>
            </div>
          </div>

          {editMode ? (
            <div className="space-y-3 p-5">
              <label className="block">
                <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">제목</div>
                <Input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
              </label>
              <label className="block">
                <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">내용 (Markdown)</div>
                <Textarea
                  value={editContent}
                  onChange={(e) => setEditContent(e.target.value)}
                  className="min-h-[520px] font-mono"
                />
              </label>
              <div className="flex items-center gap-2">
                <Button variant="primary" onClick={saveManualVersion} disabled={busy}>
                  저장(새 버전)
                </Button>
                <Button variant="ghost" onClick={() => setEditMode(false)} disabled={busy}>
                  취소
                </Button>
              </div>
            </div>
          ) : (
            <div className="relative">
              <div className="pointer-events-none absolute inset-0">
                {highlightRects.map((r, idx) => (
                  <div
                    key={idx}
                    className="absolute rounded-md bg-[color:color-mix(in_oklab,var(--accent),white_82%)]"
                    style={{
                      top: r.top,
                      left: r.left,
                      width: r.width,
                      height: Math.max(14, r.height),
                    }}
                  />
                ))}
              </div>

              <div
                ref={scrollRef}
                onMouseUp={onDocMouseUp}
                className="relative max-h-[760px] overflow-auto px-5 py-6"
              >
                {commentDraft.open && commentDraft.anchor ? (
                  <div
                    className="absolute z-20 w-[360px] max-w-[92%] rounded-2xl border border-[color:var(--line)] bg-white/95 p-4 shadow-xl backdrop-blur"
                    style={{ top: commentDraft.y, left: commentDraft.x }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-xs font-semibold text-[color:var(--ink)]">
                          코멘트 추가
                        </div>
                        <div className="mt-1 text-xs text-[color:var(--muted)]">
                          선택: “{commentDraft.anchor.quote.slice(0, 80)}
                          {commentDraft.anchor.quote.length > 80 ? "…" : ""}”
                        </div>
                      </div>
                      <button
                        className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-[color:var(--line)] bg-white/70 text-black/60 hover:bg-white"
                        onClick={() => setCommentDraft((p) => ({ ...p, open: false, anchor: null }))}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-3 grid grid-cols-[92px_1fr] items-center gap-2">
                      <div className="text-xs font-medium text-[color:var(--muted)]">타입</div>
                      <select
                        className="h-10 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                        value={commentDraft.kind}
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === "수정" || v === "좋음" || v === "대안") {
                            setCommentDraft((p) => ({ ...p, kind: v }));
                          }
                        }}
                      >
                        <option value="수정">수정</option>
                        <option value="좋음">좋음</option>
                        <option value="대안">대안</option>
                      </select>

                      <div className="text-xs font-medium text-[color:var(--muted)]">내용</div>
                      <Textarea
                        value={commentDraft.text}
                        onChange={(e) =>
                          setCommentDraft((p) => ({ ...p, text: e.target.value }))
                        }
                        placeholder="예: 이 문단에 근거 링크를 추가해줘 / 표현을 더 단정하게 바꿔줘"
                        className="min-h-24"
                      />
                    </div>

                    <div className="mt-3 flex items-center justify-end gap-2">
                      <Button variant="ghost" onClick={() => setCommentDraft((p) => ({ ...p, open: false, anchor: null }))}>
                        취소
                      </Button>
                      <Button
                        variant="primary"
                        onClick={submitComment}
                        disabled={!commentDraft.text.trim()}
                      >
                        <Check className="h-4 w-4" />
                        저장
                      </Button>
                    </div>
                  </div>
                ) : null}

                <div ref={contentRef}>
                  <article className="prose prose-zinc max-w-none prose-headings:font-[family-name:var(--font-display)] prose-p:text-[color:var(--ink)] prose-li:text-[color:var(--ink)] prose-strong:text-[color:var(--ink)]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {activeVersion?.content || ""}
                    </ReactMarkdown>
                  </article>
                </div>
              </div>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card variant="strong" className="p-5">
            <div className="text-sm font-semibold text-[color:var(--ink)]">코멘트</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              반영/거절을 남기면 히스토리에 저장됩니다.
            </div>

            <div className="mt-4 space-y-2">
              {threads.map((t) => {
                const c = t.root;
                const selected = activeThreadId === t.threadId || activeCommentId === c.commentId;
                const replyOpen = replyDraft.threadId === t.threadId;
                return (
                  <div
                    key={t.threadId}
                    className={cn(
                      "rounded-2xl border border-[color:var(--line)] bg-white/70 p-3",
                      selected && "ring-2 ring-[color:var(--accent)]",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        onClick={() => {
                          setActiveThreadId(t.threadId);
                          setActiveCommentId(c.commentId);
                        }}
                        className="min-w-0 flex-1 text-left"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          {badgeForKind(c.kind)}
                          {badgeForStatus(c.status)}
                          {t.replies.length ? (
                            <Badge tone="neutral">답글 {t.replies.length}</Badge>
                          ) : null}
                          <span className="text-xs text-[color:var(--muted)]">
                            {c.createdBy || "멤버"} · {c.createdAt?.slice(0, 16).replace("T", " ")}
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-[color:var(--ink)]">{c.text}</div>
                        <div className="mt-2 rounded-xl border border-[color:var(--line)] bg-white/60 px-3 py-2 text-xs text-[color:var(--muted)]">
                          “{c.anchor.quote.slice(0, 120)}
                          {c.anchor.quote.length > 120 ? "…" : ""}”
                        </div>
                      </button>

                      <div className="flex flex-col items-end gap-2">
                        <select
                          className="h-9 rounded-xl border border-[color:var(--line)] bg-white/80 px-2 text-xs text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                          value={c.status}
                          onChange={(e) => {
                            const v = e.target.value;
                            if (v === "open" || v === "accepted" || v === "rejected") {
                              setStatus(c.commentId, v);
                            }
                          }}
                        >
                          <option value="open">오픈</option>
                          <option value="accepted">반영</option>
                          <option value="rejected">거절</option>
                        </select>
                        <Button
                          variant="ghost"
                          className="h-9 px-3 text-xs"
                          onClick={() => {
                            setActiveThreadId(t.threadId);
                            setActiveCommentId(c.commentId);
                            setReplyDraft({ threadId: t.threadId, kind: "대안", text: "" });
                          }}
                        >
                          답글
                        </Button>
                      </div>
                    </div>

                    {selected ? (
                      <div className="mt-3 space-y-2">
                        {t.replies.map((r) => (
                          <div
                            key={r.commentId}
                            className="ml-3 rounded-2xl border border-[color:var(--line)] bg-white/60 p-3"
                          >
                            <div className="text-xs text-[color:var(--muted)]">
                              {r.createdBy || "멤버"} · {r.createdAt?.slice(0, 16).replace("T", " ")}
                            </div>
                            <div className="mt-1 text-sm text-[color:var(--ink)]">{r.text}</div>
                          </div>
                        ))}

                        {replyOpen ? (
                          <div className="ml-3 rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                            <div className="grid grid-cols-[92px_1fr] items-center gap-2">
                              <div className="text-xs font-medium text-[color:var(--muted)]">타입</div>
                              <select
                                className="h-10 rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
                                value={replyDraft.kind}
                                onChange={(e) => {
                                  const v = e.target.value;
                                  if (v === "수정" || v === "좋음" || v === "대안") {
                                    setReplyDraft((p) => ({ ...p, kind: v }));
                                  }
                                }}
                              >
                                <option value="대안">대안</option>
                                <option value="수정">수정</option>
                                <option value="좋음">좋음</option>
                              </select>

                              <div className="text-xs font-medium text-[color:var(--muted)]">내용</div>
                              <Textarea
                                value={replyDraft.text}
                                onChange={(e) => setReplyDraft((p) => ({ ...p, text: e.target.value }))}
                                placeholder="예: 왜 이 수정이 필요한지 / 참고 링크 / 다른 표현안"
                                className="min-h-20"
                              />
                            </div>

                            <div className="mt-3 flex items-center justify-end gap-2">
                              <Button
                                variant="ghost"
                                onClick={() => setReplyDraft({ threadId: null, kind: "대안", text: "" })}
                              >
                                취소
                              </Button>
                              <Button
                                variant="primary"
                                onClick={() => submitReply(t)}
                                disabled={!replyDraft.text.trim()}
                              >
                                저장
                              </Button>
                            </div>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}

              {!threads.length ? (
                <div className="rounded-2xl border border-[color:var(--line)] bg-white/60 p-4 text-sm text-[color:var(--muted)]">
                  텍스트를 드래그해 코멘트를 남겨보세요.
                </div>
              ) : null}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
