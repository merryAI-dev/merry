"use client";

import * as React from "react";

import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

type PresenceMember = {
  memberKey: string;
  memberName: string;
  memberImage?: string;
  lastSeenAt: string;
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json?.error || "FAILED");
  return json as T;
}

function initials(name: string) {
  const s = (name ?? "").trim();
  if (!s) return "?";
  const parts = s.split(/\s+/).filter(Boolean);
  const first = parts[0] ?? s;
  return first.slice(0, 2).toUpperCase();
}

export function PresenceBar({ sessionId }: { sessionId: string }) {
  const [members, setMembers] = React.useState<PresenceMember[]>([]);

  const load = React.useCallback(async () => {
    try {
      const res = await fetchJson<{ members: PresenceMember[] }>(
        `/api/presence?scope=report&scopeId=${encodeURIComponent(sessionId)}`,
      );
      setMembers(res.members || []);
    } catch {
      // ignore (presence is best-effort)
    }
  }, [sessionId]);

  const heartbeat = React.useCallback(async () => {
    try {
      await fetchJson("/api/presence", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scope: "report", scopeId: sessionId }),
      });
    } catch {
      // ignore
    }
  }, [sessionId]);

  React.useEffect(() => {
    if (!sessionId) return;
    heartbeat();
    load();
    const h = setInterval(heartbeat, 20_000);
    const p = setInterval(load, 5_000);
    return () => {
      clearInterval(h);
      clearInterval(p);
    };
  }, [sessionId, heartbeat, load]);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <div className="text-xs font-medium text-[color:var(--muted)]">온라인</div>
        <Badge tone="neutral">{members.length}</Badge>
      </div>

      <div className="flex items-center">
        <div className="flex -space-x-2">
          {members.slice(0, 6).map((m) => (
            <div
              key={m.memberKey}
              title={m.memberName}
              className="h-8 w-8 overflow-hidden rounded-full border border-white/70 bg-white/80 shadow-sm"
            >
              {m.memberImage ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={m.memberImage}
                  alt={m.memberName}
                  className="h-full w-full object-cover"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className={cn("flex h-full w-full items-center justify-center text-[11px] font-semibold text-black/70")}>
                  {initials(m.memberName)}
                </div>
              )}
            </div>
          ))}
        </div>
        {members.length > 6 ? (
          <div className="ml-2 text-xs text-[color:var(--muted)]">+{members.length - 6}</div>
        ) : null}
      </div>
    </div>
  );
}

