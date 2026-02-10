"use client";

import * as React from "react";
import { ClipboardList, FileText, LayoutDashboard, LineChart, LogOut, TrendingUp, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import type { WorkspaceSession } from "@/lib/workspace";

const nav = [
  { href: "/hub", label: "협업 허브", icon: LayoutDashboard },
  { href: "/analysis", label: "분석", icon: UploadCloud },
  { href: "/exit-projection", label: "Exit 프로젝션", icon: TrendingUp },
  { href: "/funds", label: "펀드", icon: LineChart },
  { href: "/drafts", label: "드래프트", icon: FileText },
  { href: "/report", label: "투자심사", icon: ClipboardList },
];

export function Sidebar({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);

  async function logout() {
    setBusy(true);
    try {
      await fetch("/api/auth/logout", { method: "POST" });
    } finally {
      router.replace("/");
      setBusy(false);
    }
  }

  return (
    <aside className="sticky top-4 h-[calc(100vh-2rem)] w-72 shrink-0">
      <div className="m-card-strong flex h-full flex-col rounded-3xl p-4">
        <div className="px-2 pb-3">
          <div className="flex items-baseline gap-2">
            <div className="font-[family-name:var(--font-display)] text-2xl tracking-tight">
              Merry
            </div>
            <div className="text-xs font-medium text-[color:var(--muted)]">
              VC workspace
            </div>
          </div>
          <div className="mt-2 text-sm text-[color:var(--muted)]">
            팀{" "}
            <span className="font-mono text-[color:var(--ink)]">
              {workspace.teamId}
            </span>{" "}
            ·{" "}
            <span className="font-medium text-[color:var(--ink)]">
              {workspace.memberName}
            </span>
          </div>
        </div>

        <nav className="mt-2 flex flex-col gap-1 px-1">
          {nav.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "group flex items-center gap-3 rounded-2xl px-3 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-[color:color-mix(in_oklab,var(--accent),white_86%)] text-[color:var(--ink)]"
                    : "text-[color:var(--ink)] hover:bg-black/5",
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4",
                    active ? "text-[color:var(--accent)]" : "text-black/60",
                  )}
                />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto px-1 pt-4">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={logout}
            disabled={busy}
          >
            <LogOut className="h-4 w-4" />
            로그아웃
          </Button>
        </div>
      </div>
    </aside>
  );
}
