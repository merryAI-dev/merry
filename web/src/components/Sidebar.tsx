"use client";

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  FileText,
  LayoutDashboard,
  LineChart,
  LogOut,
  TrendingUp,
  UploadCloud,
} from "lucide-react";
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

const STORAGE_KEY = "merry-sidebar-collapsed";

export function Sidebar({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(false);

  // Persist sidebar state
  React.useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "true") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  }

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
    <aside
      className={cn(
        "sticky top-3 h-[calc(100vh-1.5rem)] shrink-0 transition-all duration-300 ease-in-out",
        collapsed ? "w-16" : "w-60",
      )}
    >
      <div className="m-card-strong flex h-full flex-col rounded-2xl p-3 relative">
        {/* Toggle button */}
        <button
          onClick={toggle}
          className="absolute -right-3 top-6 z-10 flex h-6 w-6 items-center justify-center rounded-full border border-[color:var(--line)] bg-white shadow-sm hover:bg-[color:var(--bg-subtle)] transition-colors"
          aria-label={collapsed ? "사이드바 열기" : "사이드바 접기"}
        >
          {collapsed ? (
            <ChevronRight className="h-3.5 w-3.5 text-[color:var(--muted)]" />
          ) : (
            <ChevronLeft className="h-3.5 w-3.5 text-[color:var(--muted)]" />
          )}
        </button>

        {/* Header */}
        <div className={cn("px-1 pb-2", collapsed && "flex flex-col items-center")}>
          {collapsed ? (
            <div className="font-[family-name:var(--font-display)] text-lg tracking-tight">
              M
            </div>
          ) : (
            <>
              <div className="flex items-baseline gap-2">
                <div className="font-[family-name:var(--font-display)] text-xl tracking-tight">
                  Merry
                </div>
                <div className="text-[10px] font-medium text-[color:var(--muted)]">
                  VC workspace
                </div>
              </div>
              <div className="mt-1.5 text-xs text-[color:var(--muted)]">
                팀{" "}
                <span className="font-mono text-[color:var(--ink)]">
                  {workspace.teamId}
                </span>{" "}
                ·{" "}
                <span className="font-medium text-[color:var(--ink)]">
                  {workspace.memberName}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Nav */}
        <nav className="mt-1 flex flex-col gap-0.5">
          {nav.map((item) => {
            const Icon = item.icon;
            const active =
              pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group flex items-center rounded-xl text-sm font-medium transition-colors",
                  collapsed
                    ? "justify-center px-2 py-2.5"
                    : "gap-3 px-3 py-2",
                  active
                    ? "bg-[color:color-mix(in_oklab,var(--accent),white_86%)] text-[color:var(--ink)]"
                    : "text-[color:var(--ink)] hover:bg-black/5",
                )}
              >
                <Icon
                  className={cn(
                    "h-4 w-4 shrink-0",
                    active ? "text-[color:var(--accent)]" : "text-black/60",
                  )}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="mt-auto pt-3">
          {collapsed ? (
            <button
              onClick={logout}
              disabled={busy}
              title="로그아웃"
              className="flex w-full items-center justify-center rounded-xl px-2 py-2.5 text-[color:var(--muted)] hover:bg-black/5 transition-colors"
            >
              <LogOut className="h-4 w-4" />
            </button>
          ) : (
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={logout}
              disabled={busy}
            >
              <LogOut className="h-4 w-4" />
              로그아웃
            </Button>
          )}
        </div>
      </div>
    </aside>
  );
}
