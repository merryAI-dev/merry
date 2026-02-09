import { NextResponse } from "next/server";
import { z } from "zod";

import { addDraftVersion, getDraftDetail } from "@/lib/drafts";
import { completeText } from "@/lib/llm";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  baseVersionId: z.string().optional(),
});

export async function POST(
  req: Request,
  ctx: { params: Promise<{ draftId: string }> },
) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { draftId } = await ctx.params;
    const body = BodySchema.parse(await req.json());

    const detail = await getDraftDetail(ws.teamId, draftId);
    const versions = detail.versions;
    if (versions.length === 0) {
      return NextResponse.json({ ok: false, error: "NO_VERSION" }, { status: 400 });
    }

    const baseVersionId = body.baseVersionId || versions[versions.length - 1].versionId;
    const base = versions.find((v) => v.versionId === baseVersionId) ?? versions[versions.length - 1];

    const accepted = detail.comments.filter(
      (c) =>
        c.status === "accepted" &&
        c.versionId === base.versionId &&
        c.kind !== "좋음" &&
        !c.parentId,
    );
    if (accepted.length === 0) {
      return NextResponse.json({ ok: false, error: "NO_ACCEPTED_COMMENTS" }, { status: 400 });
    }

    const model = process.env.ANTHROPIC_DRAFT_MODEL;
    const maxTokens = Number(process.env.ANTHROPIC_DRAFT_MAX_TOKENS ?? "2200");

    const system =
      "You are an expert Korean editor for VC investment memos. " +
      "Apply the requested edits to the given Markdown document. " +
      "Return ONLY the updated Markdown. No code fences, no explanations.";

    const edits = accepted.map((c, i) => ({
      n: i + 1,
      kind: c.kind,
      quote: c.anchor.quote,
      context: c.anchor.context ?? "",
      instruction: c.text,
    }));

    const user =
      `원문 Markdown:\n---\n${base.content}\n---\n\n` +
      `수정 요청 목록(JSON):\n${JSON.stringify(edits)}\n\n` +
      "규칙:\n" +
      "- 가능하면 원문의 구조/톤/헤더를 유지\n" +
      "- 수정 요청이 없는 부분은 변경하지 않기\n" +
      "- 숫자/고유명사/표기 오류를 만들지 않기\n" +
      "- 결과는 Markdown만 출력\n";

    const resp = await completeText({
      system,
      maxTokens,
      model: model ?? undefined,
      temperature: 0.1,
      messages: [{ role: "user", content: user }],
    });
    const updated = resp.text.trim();

    if (!updated) {
      return NextResponse.json({ ok: false, error: "EMPTY_MODEL_OUTPUT" }, { status: 500 });
    }

    const newTitle = `${base.title} · 반영`;
    const { versionId } = await addDraftVersion({
      teamId: ws.teamId,
      draftId,
      createdBy: ws.memberName,
      title: newTitle,
      content: updated,
    });

    return NextResponse.json({
      ok: true,
      versionId,
      content: updated,
      usage: resp.usage,
      provider: resp.provider,
      model: resp.model,
    });
  } catch (err) {
    const status = err instanceof Error && err.message === "UNAUTHORIZED" ? 401 : 500;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_LLM_CONFIG"
        : "FAILED";
    return NextResponse.json({ ok: false, error: code }, { status });
  }
}
