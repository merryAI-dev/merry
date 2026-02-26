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

import { cn } from "@/lib/cn";
import type { WorkspaceSession } from "@/lib/workspace";

const nav = [
  { href: "/hub",             label: "협업 허브",     icon: LayoutDashboard },
  { href: "/analysis",        label: "분석",          icon: UploadCloud },
  { href: "/exit-projection", label: "Exit 프로젝션", icon: TrendingUp },
  { href: "/funds",           label: "펀드",          icon: LineChart },
  { href: "/drafts",          label: "드래프트",      icon: FileText },
  { href: "/report",          label: "투자심사",      icon: ClipboardList },
];

const STORAGE_KEY = "merry-sidebar-collapsed";

export function Sidebar({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(false);

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
        collapsed ? "w-[68px]" : "w-56",
      )}
    >
      <div
        className="flex h-full flex-col rounded-2xl bg-white relative"
        style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06), 0 0 0 1px #E5E8EB" }}
      >
        {/* Toggle button */}
        <button
          onClick={toggle}
          className="absolute -right-3 top-6 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-white border border-[#E5E8EB] shadow-sm hover:bg-[#F2F4F6] transition-colors"
          aria-label={collapsed ? "사이드바 열기" : "사이드바 접기"}
        >
          {collapsed
            ? <ChevronRight className="h-3.5 w-3.5 text-[#8B95A1]" />
            : <ChevronLeft  className="h-3.5 w-3.5 text-[#8B95A1]" />}
        </button>

        {/* Header */}
        <div className={cn("px-4 pt-5 pb-4 border-b border-[#F2F4F6]", collapsed && "flex flex-col items-center px-2")}>
          {collapsed ? (
            <div className="w-8 h-8 rounded-xl bg-[#3182F6] flex items-center justify-center">
              <span className="text-white font-black text-sm">M</span>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[#3182F6] flex items-center justify-center shrink-0">
                  <span className="text-white font-black text-xs">M</span>
                </div>
                <span className="font-bold text-[#191F28] text-[15px] tracking-tight">Merry</span>
              </div>
              <div className="mt-2.5 text-[11px] text-[#8B95A1] leading-snug">
                {workspace.teamId} · <span className="text-[#4E5968] font-medium">{workspace.memberName}</span>
              </div>
            </>
          )}
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 flex flex-col gap-0.5 overflow-y-auto">
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                className={cn(
                  "group relative flex items-center rounded-xl text-[13.5px] font-medium",
                  "transition-all duration-150",
                  collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2",
                  active
                    ? "bg-[#EBF3FF] text-[#3182F6]"
                    : "text-[#4E5968] hover:bg-[#F2F4F6] hover:text-[#191F28]",
                )}
              >
                {/* Left border indicator */}
                {!collapsed && (
                  <span
                    className={cn(
                      "absolute left-0 top-1 bottom-1 w-[3px] rounded-full transition-all duration-150",
                      active
                        ? "bg-[#3182F6]"
                        : "bg-transparent group-hover:bg-[#D1D6DC]",
                    )}
                  />
                )}
                <Icon
                  className={cn(
                    "h-[18px] w-[18px] shrink-0 transition-colors duration-150",
                    active
                      ? "text-[#3182F6]"
                      : "text-[#B0B8C1] group-hover:text-[#4E5968]",
                  )}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Logout */}
        <div className="px-2 pb-3 border-t border-[#F2F4F6] pt-2">
          <button
            onClick={logout}
            disabled={busy}
            title={collapsed ? "로그아웃" : undefined}
            className={cn(
              "group relative flex w-full items-center rounded-xl text-[13px] font-medium",
              "text-[#B0B8C1] hover:bg-[#F2F4F6] hover:text-[#4E5968]",
              "transition-all duration-150 disabled:opacity-40",
              collapsed ? "justify-center py-2.5" : "gap-3 px-3 py-2",
            )}
          >
            {!collapsed && (
              <span className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full bg-transparent group-hover:bg-[#D1D6DC] transition-all duration-150" />
            )}
            <LogOut className="h-[18px] w-[18px] shrink-0 transition-colors duration-150" />
            {!collapsed && <span>로그아웃</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}
