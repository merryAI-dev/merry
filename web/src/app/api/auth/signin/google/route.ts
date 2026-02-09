export const runtime = "nodejs";

import { handlers } from "@/auth";

// NextAuth expects provider sign-in to happen via POST (CSRF-protected).
// If someone opens the URL directly (GET), bounce them back to the homepage.
export async function GET(req: Request) {
  const url = new URL(req.url);
  const dest = new URL("/", url.origin);
  const callbackUrl = url.searchParams.get("callbackUrl");
  if (callbackUrl) dest.searchParams.set("callbackUrl", callbackUrl);
  dest.searchParams.set("error", "UseGoogleButton");
  return Response.redirect(dest.toString(), 302);
}

export const POST = handlers.POST;

