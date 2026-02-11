import { SendMessageCommand } from "@aws-sdk/client-sqs";
import { NextResponse } from "next/server";
import { z } from "zod";

import { getSqsClient } from "@/lib/aws/sqs";
import { getSqsQueueUrl } from "@/lib/aws/env";
import { createJob, getUploadFile, type JobType } from "@/lib/jobStore";
import { getAssumptionPackById, saveComputeSnapshot } from "@/lib/reportAssumptionsStore";
import { getAssumptionNumber, getAssumptionNumberArray, getAssumptionString } from "@/lib/assumptionPackValidators";
import type { ComputeSnapshot } from "@/lib/reportPacks";
import { requireWorkspaceFromCookies } from "@/lib/workspaceServer";

export const runtime = "nodejs";

const BodySchema = z.object({
  packId: z.string().min(6),
  fileId: z.string().min(6),
});

export async function POST(req: Request, ctx: { params: Promise<{ sessionId: string }> }) {
  try {
    const ws = await requireWorkspaceFromCookies();
    const { sessionId } = await ctx.params;
    if (!sessionId.startsWith("report_")) {
      return NextResponse.json({ ok: false, error: "BAD_SESSION" }, { status: 400 });
    }

    const body = BodySchema.parse(await req.json());
    const pack = await getAssumptionPackById(ws.teamId, sessionId, body.packId);
    if (!pack) return NextResponse.json({ ok: false, error: "PACK_NOT_FOUND" }, { status: 404 });
    if (pack.status !== "locked") return NextResponse.json({ ok: false, error: "PACK_NOT_LOCKED" }, { status: 400 });

    const file = await getUploadFile(ws.teamId, body.fileId);
    if (!file) return NextResponse.json({ ok: false, error: "FILE_NOT_FOUND" }, { status: 404 });
    if (file.status !== "uploaded") return NextResponse.json({ ok: false, error: "FILE_NOT_UPLOADED" }, { status: 400 });

    const targetYear = getAssumptionNumber(pack, "target_year");
    const perMultiples = getAssumptionNumberArray(pack, "per_multiples");
    const investmentAmount = getAssumptionNumber(pack, "investment_amount");
    const shares = getAssumptionNumber(pack, "shares");
    const totalShares = getAssumptionNumber(pack, "total_shares");
    const pricePerShare = getAssumptionNumber(pack, "price_per_share");
    const netIncomeTargetYear = getAssumptionNumber(pack, "net_income_target_year");

    const investmentYearRaw = getAssumptionNumber(pack, "investment_year");
    const investmentDate = getAssumptionString(pack, "investment_date");
    const parsedYear =
      investmentYearRaw ??
      (investmentDate && /^\d{4}/.test(investmentDate) ? Number(investmentDate.slice(0, 4)) : undefined);
    const investmentYear = typeof parsedYear === "number" && Number.isFinite(parsedYear) ? parsedYear : undefined;

    if (typeof targetYear !== "number" || !Number.isFinite(targetYear)) {
      return NextResponse.json({ ok: false, error: "MISSING_TARGET_YEAR" }, { status: 400 });
    }
    if (!perMultiples?.length) {
      return NextResponse.json({ ok: false, error: "MISSING_PER_MULTIPLES" }, { status: 400 });
    }
    if (typeof investmentAmount !== "number" || !Number.isFinite(investmentAmount)) {
      return NextResponse.json({ ok: false, error: "MISSING_INVESTMENT_AMOUNT" }, { status: 400 });
    }
    if (typeof shares !== "number" || !Number.isFinite(shares)) {
      return NextResponse.json({ ok: false, error: "MISSING_SHARES" }, { status: 400 });
    }
    if (typeof totalShares !== "number" || !Number.isFinite(totalShares)) {
      return NextResponse.json({ ok: false, error: "MISSING_TOTAL_SHARES" }, { status: 400 });
    }
    if (typeof netIncomeTargetYear !== "number" || !Number.isFinite(netIncomeTargetYear)) {
      return NextResponse.json({ ok: false, error: "MISSING_NET_INCOME" }, { status: 400 });
    }
    if (typeof investmentYear !== "number" || !Number.isFinite(investmentYear)) {
      return NextResponse.json({ ok: false, error: "MISSING_INVESTMENT_YEAR" }, { status: 400 });
    }
    if (investmentYear && investmentYear >= targetYear) {
      return NextResponse.json({ ok: false, error: "BAD_INVESTMENT_YEAR" }, { status: 400 });
    }

    const jobId = crypto.randomUUID().replaceAll("-", "").slice(0, 16);
    const createdAt = new Date().toISOString();
    const type = "exit_projection" as JobType;
    const title = pack.companyName ? `Exit 프로젝션 · ${pack.companyName}` : "Exit 프로젝션";

    await createJob({
      jobId,
      teamId: ws.teamId,
      type,
      status: "queued",
      title,
      createdBy: ws.memberName,
      createdAt,
      inputFileIds: [body.fileId],
      params: {
        targetYear,
        perMultiples,
        ...(investmentYear ? { investmentYear } : {}),
        investmentAmount,
        shares,
        totalShares,
        ...(typeof pricePerShare === "number" && Number.isFinite(pricePerShare) ? { pricePerShare } : {}),
        netIncomeTargetYear,
        companyName: pack.companyName,
        packId: pack.packId,
        sessionId,
      },
    });

    const snapshot: ComputeSnapshot = {
      snapshotId: crypto.randomUUID(),
      sessionId,
      packId: pack.packId,
      jobId,
      createdAt,
      createdBy: ws.memberName,
      derivedSummary: {
        target_year: targetYear,
        investment_year: investmentYear,
        investment_amount: investmentAmount,
        shares,
        total_shares: totalShares,
        price_per_share: pricePerShare,
        net_income_target_year: netIncomeTargetYear,
        per_multiples: perMultiples,
      },
    };
    await saveComputeSnapshot({ teamId: ws.teamId, sessionId, snapshot });

    const sqs = getSqsClient();
    await sqs.send(
      new SendMessageCommand({
        QueueUrl: getSqsQueueUrl(),
        MessageBody: JSON.stringify({ teamId: ws.teamId, jobId }),
      }),
    );

    return NextResponse.json({ ok: true, jobId });
  } catch (err) {
    const unauthorized = err instanceof Error && err.message === "UNAUTHORIZED";
    const status = unauthorized ? 401 : 400;
    const code =
      err instanceof Error && err.message.startsWith("Missing env ")
        ? "MISSING_AWS_CONFIG"
        : "BAD_REQUEST";
    return NextResponse.json({ ok: false, error: unauthorized ? "UNAUTHORIZED" : code }, { status });
  }
}
