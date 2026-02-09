import { SignJWT, jwtVerify } from "jose";

export const WORKSPACE_COOKIE_NAME = "merry_ws";

export type WorkspaceSession = {
  teamId: string;
  memberName: string;
};

const encoder = new TextEncoder();

function getJwtSecret(): Uint8Array {
  const secret = process.env.WORKSPACE_JWT_SECRET;
  if (!secret) {
    throw new Error("Missing env WORKSPACE_JWT_SECRET");
  }
  return encoder.encode(secret);
}

export async function signWorkspaceSession(session: WorkspaceSession): Promise<string> {
  return await new SignJWT(session)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("30d")
    .sign(getJwtSecret());
}

export async function verifyWorkspaceSession(token: string): Promise<WorkspaceSession | null> {
  try {
    const { payload } = await jwtVerify(token, getJwtSecret());
    const teamId = typeof payload.teamId === "string" ? payload.teamId : "";
    const memberName = typeof payload.memberName === "string" ? payload.memberName : "";
    if (!teamId || !memberName) return null;
    return { teamId, memberName };
  } catch {
    return null;
  }
}

export function getExpectedPasscode(teamId: string): string | null {
  // Global passcode for all teams (simplest).
  const global = process.env.WORKSPACE_CODE;
  if (global) return global;

  // Optional: per-team passcodes.
  // Example: WORKSPACE_TEAM_1_CODE, WORKSPACE_TEAM_2_CODE, ...
  const m = /^team_(\\d+)$/.exec(teamId);
  if (!m) return null;
  const envKey = `WORKSPACE_TEAM_${m[1]}_CODE`;
  return process.env[envKey] ?? null;
}

