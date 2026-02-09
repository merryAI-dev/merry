import { NextResponse } from "next/server";

import { WORKSPACE_COOKIE_NAME } from "@/lib/workspace";

export const runtime = "nodejs";

export async function POST() {
  const res = NextResponse.json({ ok: true });

  const secure = process.env.NODE_ENV === "production";
  const base = {
    httpOnly: true,
    sameSite: "lax" as const,
    secure,
    path: "/",
    maxAge: 0,
  };

  // Legacy workspace cookie.
  res.cookies.set(WORKSPACE_COOKIE_NAME, "", base);

  // NextAuth/Auth.js cookies (v5 + legacy names) for a clean logout without CSRF.
  for (const name of [
    "authjs.session-token",
    "__Secure-authjs.session-token",
    "authjs.csrf-token",
    "__Host-authjs.csrf-token",
    "authjs.callback-url",
    "__Secure-authjs.callback-url",
    "next-auth.session-token",
    "__Secure-next-auth.session-token",
    "next-auth.csrf-token",
    "next-auth.callback-url",
  ]) {
    res.cookies.set(name, "", base);
  }

  return res;
}
