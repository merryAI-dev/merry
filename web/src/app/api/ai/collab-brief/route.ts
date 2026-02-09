import { NextResponse } from "next/server";

import { listTeamDocs } from "@/lib/teamDocs";
import { listTeamEvents } from "@/lib/teamCalendar";
import { listTeamComments } from "@/lib/teamComments";
import { listTeamTasks } from "@/lib/teamTasks";
import { completeText } from "@/lib/llm";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

function extractJson(text: string) {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("No JSON object found in model output");
  }
  return JSON.parse(text.slice(start, end + 1));
}

export async function POST() {
  try {
    const ws = await requireWorkspaceFromCookies();

    const [tasks, docs, events, comments] = await Promise.all([
      listTeamTasks(ws.teamId, true, 80),
      listTeamDocs(ws.teamId),
      listTeamEvents(ws.teamId, 30),
      listTeamComments(ws.teamId, 20),
    ]);

    const model = process.env.ANTHROPIC_BRIEF_MODEL;
    const maxTokens = Number(process.env.ANTHROPIC_BRIEF_MAX_TOKENS ?? "900");

    const system =
      "You are a collaboration COO for a VC team. Return JSON only. Write in Korean. " +
      "Provide concise, action-oriented guidance.";

    const payload = { tasks, docs, events, comments };
    const user = `팀 데이터:\n${JSON.stringify(payload)}\n\nOutput JSON schema:\n{\n  \"today_focus\": [\"...\"],\n  \"task_risks\": [\"...\"],\n  \"doc_gaps\": [\"...\"],\n  \"required_docs\": [\"...\"],\n  \"next_actions\": [\"...\"],\n  \"questions\": [\"...\"]\n}\n`;

    const resp = await completeText({
      system,
      maxTokens,
      model: model ?? undefined,
      messages: [{ role: "user", content: user }],
      temperature: 0.2,
    });
    const text = resp.text.trim();

    const brief = extractJson(text);
    return NextResponse.json({ ok: true, brief, usage: resp.usage, provider: resp.provider, model: resp.model });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_LLM_CONFIG"
        : "FAILED";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
