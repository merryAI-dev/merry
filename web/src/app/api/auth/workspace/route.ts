import { NextResponse } from "next/server";
import { z } from "zod";

import {
  WORKSPACE_COOKIE_NAME,
  getExpectedPasscode,
  signWorkspaceSession,
} from "@/lib/workspace";
import { googleAuthEnabled } from "@/auth";

export const runtime = "nodejs";

const BodySchema = z.object({
  teamId: z.string().min(1),
  memberName: z.string().min(1).max(40),
  passcode: z.string().min(1),
});

export async function POST(req: Request) {
  try {
    // When Google auth is configured, disable the passcode login path to avoid bypass.
    if (googleAuthEnabled()) {
      return NextResponse.json({ ok: false, error: "DISABLED" }, { status: 410 });
    }

    const body = BodySchema.parse(await req.json());
    const expected = getExpectedPasscode(body.teamId);
    if (!expected || body.passcode !== expected) {
      return NextResponse.json({ ok: false, error: "INVALID_PASSCODE" }, { status: 401 });
    }

    const token = await signWorkspaceSession({
      teamId: body.teamId,
      memberName: body.memberName,
    });

    const res = NextResponse.json({ ok: true });
    res.cookies.set(WORKSPACE_COOKIE_NAME, token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30, // 30 days
    });
    return res;
  } catch {
    return NextResponse.json({ ok: false, error: "BAD_REQUEST" }, { status: 400 });
  }
}
