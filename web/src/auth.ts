import NextAuth from "next-auth";
import type { JWT } from "next-auth/jwt";
import type { Session } from "next-auth";
import Google from "next-auth/providers/google";

/** Extended JWT with custom workspace fields. */
interface MerryJWT extends JWT {
  teamId?: string;
  memberName?: string;
  email?: string;
}

/** Extended Session with custom workspace fields. */
interface MerrySession extends Session {
  teamId?: string;
  memberName?: string;
}

function isGoogleConfigured(): boolean {
  return Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
}

function getAllowedDomain(): string {
  return (process.env.AUTH_ALLOWED_DOMAIN ?? "mysc.co.kr").trim().toLowerCase();
}

function isAllowedEmail(email: string): boolean {
  const allowed = getAllowedDomain();
  if (!allowed) return true;
  return email.toLowerCase().endsWith("@" + allowed);
}

function getTeamId(): string {
  return (process.env.AUTH_TEAM_ID ?? "mysc").trim() || "mysc";
}

const nextAuth = isGoogleConfigured()
  ? NextAuth({
      providers: [
        Google({
          clientId: process.env.GOOGLE_CLIENT_ID ?? "",
          clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
        }),
      ],
      // Pin sign-in and error pages to our homepage.
      pages: { signIn: "/", error: "/" },
      session: { strategy: "jwt" },
      trustHost: true,
      secret:
        process.env.NEXTAUTH_SECRET ??
        process.env.AUTH_SECRET ??
        process.env.WORKSPACE_JWT_SECRET,
      callbacks: {
        async signIn({ user }) {
          const email = typeof user.email === "string" ? user.email : "";
          if (!email) return false;
          return isAllowedEmail(email);
        },
        async jwt({ token, user }) {
          if (user) {
            const email = typeof user.email === "string" ? user.email : "";
            const nameRaw = typeof user.name === "string" ? user.name : "";
            const memberName = nameRaw.trim() || (email ? email.split("@")[0] : "member");
            const t = token as MerryJWT;
            t.teamId = getTeamId();
            t.memberName = memberName;
            t.email = email;
          }
          return token;
        },
        async session({ session, token }) {
          const t = token as MerryJWT;
          const s = session as MerrySession;
          s.teamId = t.teamId ?? getTeamId();
          s.memberName =
            t.memberName ??
            (typeof session.user?.name === "string" ? session.user.name : "") ??
            "member";
          return session;
        },
      },
    })
  : null;

export const handlers = nextAuth?.handlers ?? {
  async GET() {
    return new Response("Not Found", { status: 404 });
  },
  async POST() {
    return new Response("Not Found", { status: 404 });
  },
};

export const auth = nextAuth?.auth ?? (async () => null);

export function googleAuthEnabled(): boolean {
  return isGoogleConfigured();
}

export function authAllowedDomain(): string {
  return getAllowedDomain();
}

export function authTeamId(): string {
  return getTeamId();
}
