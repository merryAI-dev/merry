import { ensureSession, getMessages, addMessage } from "@/lib/chatStore";

export type TeamTaskStatus = "todo" | "in_progress" | "done" | "blocked";

export type TeamTask = {
  id: string;
  title: string;
  status: TeamTaskStatus;
  owner: string;
  due_date: string;
  notes: string;
  created_at?: string;
  updated_at?: string;
};

export const STATUS_LABELS: Record<TeamTaskStatus, string> = {
  todo: "진행 전",
  in_progress: "진행 중",
  done: "완료",
  blocked: "진행 중",
};

export function normalizeStatus(status: string): "todo" | "in_progress" | "done" {
  if (status === "blocked") return "in_progress";
  if (status === "in_progress" || status === "done") return status;
  return "todo";
}

function isTaskStatus(value: unknown): value is TeamTaskStatus {
  return value === "todo" || value === "in_progress" || value === "done" || value === "blocked";
}

export function formatRemainingKst(dueDateIso: string): string {
  if (!dueDateIso) return "";
  const due = new Date(dueDateIso.includes("T") ? dueDateIso : `${dueDateIso}T23:59:59+09:00`);
  if (Number.isNaN(due.getTime())) return "";
  const now = new Date();
  const deltaMs = due.getTime() - now.getTime();
  const seconds = Math.floor(deltaMs / 1000);
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

function taskSessionId(teamId: string) {
  return `tasks_${teamId}`;
}

export async function listTeamTasks(teamId: string, includeDone = true, limit = 60): Promise<TeamTask[]> {
  const tasks: Record<string, TeamTask> = {};
  const messages = await getMessages(teamId, taskSessionId(teamId));

  for (const msg of messages) {
    if (msg.role !== "team_task") continue;
    const meta = (msg.metadata ?? {}) as Record<string, unknown>;
    const taskId = typeof meta["task_id"] === "string" ? meta["task_id"] : undefined;
    if (!taskId) continue;

    const current = tasks[taskId];
    if (!current) {
      const title = typeof meta["title"] === "string" ? meta["title"] : msg.content || "";
      const status = isTaskStatus(meta["status"]) ? meta["status"] : "todo";
      const owner = typeof meta["owner"] === "string" ? meta["owner"] : "";
      const due_date = typeof meta["due_date"] === "string" ? meta["due_date"] : "";
      const notes = typeof meta["notes"] === "string" ? meta["notes"] : "";
      const created_at = typeof meta["created_at"] === "string" ? meta["created_at"] : msg.created_at;
      const updated_at = typeof meta["updated_at"] === "string" ? meta["updated_at"] : msg.created_at;

      tasks[taskId] = {
        id: taskId,
        title,
        status,
        owner,
        due_date,
        notes,
        created_at,
        updated_at,
      };
      continue;
    }

    if (typeof meta["title"] === "string") current.title = meta["title"] || current.title;
    if (isTaskStatus(meta["status"])) current.status = meta["status"];
    if (typeof meta["owner"] === "string") current.owner = meta["owner"] || "";
    if (typeof meta["due_date"] === "string") current.due_date = meta["due_date"] || "";
    if (typeof meta["notes"] === "string") current.notes = meta["notes"] || "";
    const updated_at = typeof meta["updated_at"] === "string" ? meta["updated_at"] : undefined;
    const created_at = typeof meta["created_at"] === "string" ? meta["created_at"] : undefined;
    current.updated_at = updated_at || created_at || msg.created_at;
  }

  let values = Object.values(tasks);
  if (!includeDone) {
    values = values.filter((t) => normalizeStatus(t.status) !== "done");
  }

  const statusOrder: Record<string, number> = { todo: 1, in_progress: 2, done: 3 };
  values.sort((a, b) => {
    const ao = statusOrder[normalizeStatus(a.status)] ?? 9;
    const bo = statusOrder[normalizeStatus(b.status)] ?? 9;
    if (ao !== bo) return ao - bo;
    const ad = a.due_date || "9999-12-31";
    const bd = b.due_date || "9999-12-31";
    return ad.localeCompare(bd);
  });

  return values.slice(0, limit);
}

export async function addTeamTask(args: {
  teamId: string;
  createdBy: string;
  title: string;
  owner?: string;
  due_date?: string;
  notes?: string;
}): Promise<TeamTask> {
  const now = new Date().toISOString();
  const id = crypto.randomUUID().replaceAll("-", "").slice(0, 12);
  const task: TeamTask = {
    id,
    title: args.title.trim(),
    status: "todo",
    owner: (args.owner ?? "").trim(),
    due_date: args.due_date ?? "",
    notes: (args.notes ?? "").trim(),
    created_at: now,
    updated_at: now,
  };

  const sessionId = taskSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "team_tasks" });
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "team_task",
    content: task.title,
    metadata: {
      task_id: task.id,
      title: task.title,
      status: task.status,
      owner: task.owner,
      due_date: task.due_date,
      notes: task.notes,
      created_by: args.createdBy,
      created_at: task.created_at,
      updated_at: task.updated_at,
    },
  });

  return task;
}

export async function updateTeamTask(args: {
  teamId: string;
  updatedBy: string;
  taskId: string;
  title?: string;
  status?: TeamTaskStatus;
  owner?: string;
  due_date?: string;
  notes?: string;
}): Promise<void> {
  const payload: Record<string, unknown> = {
    task_id: args.taskId,
    updated_by: args.updatedBy,
    updated_at: new Date().toISOString(),
  };
  if (args.title !== undefined) payload.title = args.title.trim();
  if (args.status !== undefined) payload.status = args.status;
  if (args.owner !== undefined) payload.owner = args.owner.trim();
  if (args.due_date !== undefined) payload.due_date = args.due_date;
  if (args.notes !== undefined) payload.notes = args.notes.trim();

  const sessionId = taskSessionId(args.teamId);
  await ensureSession(args.teamId, sessionId, { type: "team_tasks" });
  const title = typeof payload["title"] === "string" ? payload["title"] : "";
  await addMessage({
    teamId: args.teamId,
    sessionId,
    role: "team_task",
    content: title || `update:${args.taskId}`,
    metadata: payload,
  });
}
