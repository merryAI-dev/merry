"use client";

import * as React from "react";
import {
  DndContext,
  PointerSensor,
  type DragEndEvent,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { GripVertical, RefreshCw, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Textarea } from "@/components/ui/Textarea";
import { cn } from "@/lib/cn";

type TeamTask = {
  id: string;
  title: string;
  status: string;
  owner: string;
  due_date: string;
  notes: string;
};

type TeamDoc = {
  id: string;
  name: string;
  required: boolean;
  uploaded: boolean;
  owner: string;
  notes: string;
};

type TeamEvent = {
  id: string;
  date: string;
  title: string;
  notes: string;
  created_by: string;
  created_at: string;
};

type TeamComment = { text: string; created_by: string; created_at: string };
type TeamActivity = {
  session_id: string;
  role: string;
  content: string;
  created_at: string;
  member: string;
};

type CollabBrief = {
  today_focus?: string[];
  task_risks?: string[];
  doc_gaps?: string[];
  required_docs?: string[];
  next_actions?: string[];
  questions?: string[];
};

function normalizeStatus(status: string) {
  if (status === "blocked") return "in_progress";
  if (status === "in_progress" || status === "done") return status;
  return "todo";
}

function remainingLabel(dueDate: string) {
  if (!dueDate) return "";
  const due = new Date(dueDate.includes("T") ? dueDate : `${dueDate}T23:59:59+09:00`);
  if (Number.isNaN(due.getTime())) return "";
  const now = new Date();
  const seconds = Math.floor((due.getTime() - now.getTime()) / 1000);
  if (seconds >= 0) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    if (days > 0) return `남은 ${days}일 ${hours}시간`;
    return `남은 ${hours}시간`;
  }
  const abs = Math.abs(seconds);
  const days = Math.floor(abs / 86400);
  if (days === 0) return "마감 지남";
  return `마감 지남 ${days}일`;
}

function Column({
  id,
  title,
  count,
  children,
}: {
  id: string;
  title: string;
  count: number;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "m-card flex min-h-[340px] flex-col rounded-3xl p-4",
        isOver && "ring-2 ring-[color:var(--accent)]",
      )}
    >
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold text-[color:var(--ink)]">{title}</div>
        <Badge tone="neutral">{count}</Badge>
      </div>
      <div className="mt-3 flex flex-col gap-2">{children}</div>
    </div>
  );
}

function TaskCard({ task }: { task: TeamTask }) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: task.id,
    data: { status: normalizeStatus(task.status) },
  });
  const style = transform
    ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)` }
    : undefined;

  const due = remainingLabel(task.due_date);
  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        "rounded-2xl border border-[color:var(--line)] bg-white/80 p-3 shadow-sm transition-shadow",
        isDragging && "shadow-lg",
      )}
    >
      <div className="flex items-start gap-2">
        <button
          className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-xl border border-[color:var(--line)] bg-white/70 text-black/60 hover:bg-white"
          {...listeners}
          {...attributes}
          aria-label="drag"
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-[color:var(--ink)]">
            {task.title}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-[color:var(--muted)]">
            <span>담당: {task.owner || "미정"}</span>
            {due ? <span>· {due}</span> : null}
          </div>
        </div>
      </div>
    </div>
  );
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

export default function HubPage() {
  const [busy, setBusy] = React.useState(false);
  const [tasks, setTasks] = React.useState<TeamTask[]>([]);
  const [docs, setDocs] = React.useState<TeamDoc[]>([]);
  const [events, setEvents] = React.useState<TeamEvent[]>([]);
  const [comments, setComments] = React.useState<TeamComment[]>([]);
  const [activity, setActivity] = React.useState<TeamActivity[]>([]);
  const [brief, setBrief] = React.useState<CollabBrief | null>(null);
  const [briefBusy, setBriefBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  async function loadAll() {
    setBusy(true);
    setError(null);
    try {
      const [t, d, c, cal, a] = await Promise.all([
        fetchJson<{ tasks: TeamTask[] }>("/api/tasks"),
        fetchJson<{ docs: TeamDoc[] }>("/api/docs"),
        fetchJson<{ comments: TeamComment[] }>("/api/comments"),
        fetchJson<{ events: TeamEvent[] }>("/api/calendar"),
        fetchJson<{ activity: TeamActivity[] }>("/api/activity"),
      ]);
      setTasks(t.tasks || []);
      setDocs(d.docs || []);
      setComments(c.comments || []);
      setEvents(cal.events || []);
      setActivity(a.activity || []);
    } catch {
      setError("데이터 로드에 실패했습니다. AWS/DynamoDB/환경변수를 확인하세요.");
    } finally {
      setBusy(false);
    }
  }

  React.useEffect(() => {
    loadAll();
  }, []);

  const todo = tasks.filter((t) => normalizeStatus(t.status) === "todo");
  const progress = tasks.filter((t) => normalizeStatus(t.status) === "in_progress");
  const done = tasks.filter((t) => normalizeStatus(t.status) === "done");

  const required = docs.filter((d) => d.required);
  const requiredUploaded = required.filter((d) => d.uploaded);

  async function onDragEnd(evt: DragEndEvent) {
    const overId = typeof evt.over?.id === "string" ? evt.over.id : null;
    const activeId = typeof evt.active?.id === "string" ? evt.active.id : null;
    if (!overId || !activeId) return;
    if (!["todo", "in_progress", "done"].includes(overId)) return;

    const task = tasks.find((t) => t.id === activeId);
    if (!task) return;
    const current = normalizeStatus(task.status);
    if (current === overId) return;

    setTasks((prev) => prev.map((t) => (t.id === activeId ? { ...t, status: overId } : t)));
    try {
      await fetchJson("/api/tasks", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ taskId: activeId, status: overId }),
      });
    } catch {
      await loadAll();
    }
  }

  const [newTaskTitle, setNewTaskTitle] = React.useState("");
  const [newTaskOwner, setNewTaskOwner] = React.useState("");
  const [newTaskDue, setNewTaskDue] = React.useState("");

  async function addTask() {
    const title = newTaskTitle.trim();
    if (!title) return;
    setNewTaskTitle("");
    try {
      await fetchJson("/api/tasks", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ title, owner: newTaskOwner, due_date: newTaskDue }),
      });
      await loadAll();
    } catch {
      setError("과업 추가에 실패했습니다.");
    }
  }

  const [newDocName, setNewDocName] = React.useState("");
  async function addDoc() {
    const name = newDocName.trim();
    if (!name) return;
    setNewDocName("");
    try {
      await fetchJson("/api/docs", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name, required: true }),
      });
      await loadAll();
    } catch {
      setError("문서 추가에 실패했습니다.");
    }
  }

  async function toggleDocUploaded(docId: string, uploaded: boolean) {
    setDocs((prev) => prev.map((d) => (d.id === docId ? { ...d, uploaded } : d)));
    try {
      await fetchJson("/api/docs", {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ docId, uploaded }),
      });
    } catch {
      await loadAll();
    }
  }

  const [newEventDate, setNewEventDate] = React.useState("");
  const [newEventTitle, setNewEventTitle] = React.useState("");
  async function addEvent() {
    if (!newEventDate || !newEventTitle.trim()) return;
    try {
      await fetchJson("/api/calendar", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ date: newEventDate, title: newEventTitle, notes: "" }),
      });
      setNewEventTitle("");
      await loadAll();
    } catch {
      setError("일정 추가에 실패했습니다.");
    }
  }

  const [newComment, setNewComment] = React.useState("");
  async function addComment() {
    const text = newComment.trim();
    if (!text) return;
    setNewComment("");
    try {
      await fetchJson("/api/comments", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      await loadAll();
    } catch {
      setError("코멘트 추가에 실패했습니다.");
    }
  }

  async function generateBrief() {
    setBriefBusy(true);
    setError(null);
    try {
      const res = await fetchJson<{ brief: CollabBrief }>("/api/ai/collab-brief", {
        method: "POST",
      });
      setBrief(res.brief);
    } catch {
      setError("AI 브리프 생성에 실패했습니다. Bedrock/LLM 환경변수와 모델 접근 권한을 확인하세요.");
    } finally {
      setBriefBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-[color:var(--muted)]">
            Team Collaboration Hub
          </div>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-3xl tracking-tight text-[color:var(--ink)]">
            팀 협업 허브
          </h1>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            과업, 서류, 일정, 코멘트를 한 화면에서 정돈합니다.
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={loadAll} disabled={busy}>
            <RefreshCw className={cn("h-4 w-4", busy && "animate-spin")} />
            새로고침
          </Button>
        </div>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-900">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <div className="text-xs font-medium text-[color:var(--muted)]">진행 전</div>
          <div className="mt-1 text-2xl font-semibold text-[color:var(--ink)]">{todo.length}</div>
        </Card>
        <Card>
          <div className="text-xs font-medium text-[color:var(--muted)]">진행 중</div>
          <div className="mt-1 text-2xl font-semibold text-[color:var(--ink)]">{progress.length}</div>
        </Card>
        <Card>
          <div className="text-xs font-medium text-[color:var(--muted)]">완료</div>
          <div className="mt-1 text-2xl font-semibold text-[color:var(--ink)]">{done.length}</div>
        </Card>
        <Card>
          <div className="text-xs font-medium text-[color:var(--muted)]">필수 서류 업로드</div>
          <div className="mt-1 text-2xl font-semibold text-[color:var(--ink)]">
            {requiredUploaded.length}/{required.length}
          </div>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.8fr_1fr]">
        <div className="space-y-4">
          <Card variant="strong" className="p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[color:var(--ink)]">
                  팀 과업 보드
                </div>
                <div className="mt-1 text-sm text-[color:var(--muted)]">
                  카드를 드래그해서 상태를 바꾸세요.
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Input
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="새 과업 제목"
                  className="w-56"
                />
                <Input
                  value={newTaskOwner}
                  onChange={(e) => setNewTaskOwner(e.target.value)}
                  placeholder="담당자"
                  className="w-32"
                />
                <Input
                  value={newTaskDue}
                  onChange={(e) => setNewTaskDue(e.target.value)}
                  placeholder="마감(YYYY-MM-DD)"
                  className="w-40"
                />
                <Button variant="primary" onClick={addTask} disabled={!newTaskTitle.trim()}>
                  추가
                </Button>
              </div>
            </div>

            <div className="mt-4">
              <DndContext sensors={sensors} onDragEnd={onDragEnd}>
                <div className="grid gap-3 md:grid-cols-3">
                  <Column id="todo" title="진행 전" count={todo.length}>
                    {todo.map((t) => (
                      <TaskCard key={t.id} task={t} />
                    ))}
                  </Column>
                  <Column id="in_progress" title="진행 중" count={progress.length}>
                    {progress.map((t) => (
                      <TaskCard key={t.id} task={t} />
                    ))}
                  </Column>
                  <Column id="done" title="완료" count={done.length}>
                    {done.map((t) => (
                      <TaskCard key={t.id} task={t} />
                    ))}
                  </Column>
                </div>
              </DndContext>
            </div>
          </Card>

          <Card variant="strong" className="p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[color:var(--ink)]">
                  메리의 협업 브리프
                </div>
                <div className="mt-1 text-sm text-[color:var(--muted)]">
                  팀 데이터를 요약해 오늘의 실행 포인트를 제안합니다.
                </div>
              </div>
              <Button variant="primary" onClick={generateBrief} disabled={briefBusy}>
                <Sparkles className={cn("h-4 w-4", briefBusy && "animate-pulse")} />
                AI 브리프 생성
              </Button>
            </div>

            {brief ? (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {(
                  [
                    ["오늘 집중", brief.today_focus],
                    ["과업 리스크", brief.task_risks],
                    ["문서 공백", brief.doc_gaps],
                    ["필수 문서 추천", brief.required_docs],
                    ["다음 액션", brief.next_actions],
                    ["확인 질문", brief.questions],
                  ] as Array<[string, string[] | undefined]>
                ).map(([title, items]) => (
                  <div key={title} className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-4">
                    <div className="text-xs font-semibold text-[color:var(--ink)]">{title}</div>
                    <div className="mt-2 space-y-1 text-sm text-[color:var(--muted)]">
                      {(items ?? []).length ? (
                        (items ?? []).slice(0, 6).map((it, idx) => (
                          <div key={idx} className="flex gap-2">
                            <span className="text-black/30">•</span>
                            <span>{it}</span>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-[color:var(--muted)]">없음</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="mt-4 text-sm text-[color:var(--muted)]">
                버튼을 누르면 브리프를 생성합니다.
              </div>
            )}
          </Card>
        </div>

        <div className="space-y-4">
          <Card variant="strong" className="p-5">
            <div className="flex items-end justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-[color:var(--ink)]">서류 체크리스트</div>
                <div className="mt-1 text-sm text-[color:var(--muted)]">
                  필수 서류 업로드를 빠르게 체크합니다.
                </div>
              </div>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center gap-2">
                <Input
                  value={newDocName}
                  onChange={(e) => setNewDocName(e.target.value)}
                  placeholder="문서 추가"
                />
                <Button variant="primary" onClick={addDoc} disabled={!newDocName.trim()}>
                  추가
                </Button>
              </div>
              <div className="max-h-72 space-y-1 overflow-auto pr-1">
                {docs.map((d) => (
                  <label
                    key={d.id}
                    className="flex cursor-pointer items-start gap-3 rounded-2xl border border-[color:var(--line)] bg-[color:var(--card)]/60 backdrop-blur-sm p-3 transition-all duration-200 hover:bg-[color:var(--card)]/90 hover:border-[color:var(--accent-purple)]/30 hover:shadow-[0_0_15px_rgba(30,64,175,0.1)]"
                  >
                    <input
                      type="checkbox"
                      className="mt-1 h-4 w-4 rounded accent-[color:var(--accent-purple)] cursor-pointer"
                      checked={Boolean(d.uploaded)}
                      onChange={(e) => toggleDocUploaded(d.id, e.target.checked)}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <div className="truncate text-sm font-medium text-[color:var(--ink)]">
                          {d.name}
                        </div>
                        {d.required ? <Badge tone="accent">필수</Badge> : <Badge>선택</Badge>}
                      </div>
                      <div className="mt-1 text-xs text-[color:var(--muted)]">
                        담당: {d.owner || "미정"}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </Card>

          <Card variant="strong" className="p-5">
            <div className="text-sm font-semibold text-[color:var(--ink)]">팀 캘린더</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">다가오는 일정 메모.</div>
            <div className="mt-4 space-y-2">
              <div className="grid grid-cols-[1fr_1.2fr_auto] gap-2">
                <Input
                  value={newEventDate}
                  onChange={(e) => setNewEventDate(e.target.value)}
                  placeholder="YYYY-MM-DD"
                />
                <Input
                  value={newEventTitle}
                  onChange={(e) => setNewEventTitle(e.target.value)}
                  placeholder="일정 제목"
                />
                <Button variant="primary" onClick={addEvent} disabled={!newEventDate || !newEventTitle.trim()}>
                  추가
                </Button>
              </div>
              <div className="max-h-56 space-y-2 overflow-auto pr-1">
                {events.map((e) => (
                  <div
                    key={e.id}
                    className="rounded-2xl border border-[color:var(--line)] bg-[color:var(--card)]/60 backdrop-blur-sm p-3 transition-all duration-200 hover:border-[color:var(--accent-cyan)]/30 hover:shadow-[0_0_15px_rgba(6,182,212,0.1)]"
                  >
                    <div className="text-xs font-medium text-[color:var(--accent-cyan)]">{e.date}</div>
                    <div className="mt-1 text-sm font-medium text-[color:var(--ink)]">{e.title}</div>
                  </div>
                ))}
                {!events.length ? (
                  <div className="text-sm text-[color:var(--muted)]">일정이 없습니다.</div>
                ) : null}
              </div>
            </div>
          </Card>

          <Card variant="strong" className="p-5">
            <div className="text-sm font-semibold text-[color:var(--ink)]">팀 코멘트</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              메모/결정사항을 짧게 남겨두세요.
            </div>
            <div className="mt-4 space-y-2">
              <Textarea
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                placeholder="코멘트 입력"
                className="min-h-24"
              />
              <Button variant="primary" onClick={addComment} disabled={!newComment.trim()}>
                추가
              </Button>
              <div className="max-h-56 space-y-2 overflow-auto pr-1">
                {comments.map((c, idx) => (
                  <div key={idx} className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                    <div className="text-xs text-[color:var(--muted)]">
                      {c.created_by || "멤버"} · {c.created_at?.slice(0, 16).replace("T", " ")}
                    </div>
                    <div className="mt-1 text-sm text-[color:var(--ink)]">{c.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card variant="strong" className="p-5">
            <div className="text-sm font-semibold text-[color:var(--ink)]">최근 활동</div>
            <div className="mt-1 text-sm text-[color:var(--muted)]">
              최근 저장된 이벤트 로그.
            </div>
            <div className="mt-4 max-h-72 space-y-2 overflow-auto pr-1">
              {activity.map((a, idx) => (
                <div key={idx} className="rounded-2xl border border-[color:var(--line)] bg-white/70 p-3">
                  <div className="text-xs text-[color:var(--muted)]">
                    {a.member || "멤버"} · {a.created_at?.slice(0, 16).replace("T", " ")}
                  </div>
                  <div className="mt-1 text-sm text-[color:var(--ink)]">
                    <span className="font-mono text-xs text-black/50">{a.role}</span>{" "}
                    {a.content}
                  </div>
                </div>
              ))}
              {!activity.length ? (
                <div className="text-sm text-[color:var(--muted)]">활동이 없습니다.</div>
              ) : null}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
