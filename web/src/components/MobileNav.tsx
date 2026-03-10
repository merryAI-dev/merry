"use client";

import * as React from "react";
import {
  AlertTriangle,
  Menu,
  X,
  ClipboardList,
  FileText,
  Files,
  FlaskConical,
  History,
  LayoutDashboard,
  LineChart,
  LogOut,
  ScanSearch,
  Settings,
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
  { href: "/documents",       label: "문서 추출",     icon: Files },
  { href: "/playground",      label: "플레이그라운드", icon: FlaskConical },
  { href: "/check",           label: "조건 검사",      icon: ScanSearch },
  { href: "/exit-projection", label: "Exit 프로젝션", icon: TrendingUp },
  { href: "/funds",           label: "펀드",          icon: LineChart },
  { href: "/drafts",          label: "드래프트",      icon: FileText },
  { href: "/report",          label: "투자심사",      icon: ClipboardList },
  { href: "/review",          label: "검토 큐",       icon: AlertTriangle },
  { href: "/history",         label: "작업 이력",     icon: History },
  { href: "/admin",           label: "관리자",        icon: Settings },
];

export function MobileNav({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  // Close on route change.
  React.useEffect(() => {
    setOpen(false);
  }, [pathname]);

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
    <>
      {/* Mobile header bar */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-[#E5E8EB] bg-white px-4 py-3 md:hidden">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#3182F6]">
            <span className="text-xs font-black text-white">M</span>
          </div>
          <span className="text-[15px] font-bold tracking-tight text-[#191F28]">Merry</span>
        </div>
        <button
          onClick={() => setOpen(!open)}
          aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
          aria-expanded={open}
          className="rounded-lg p-2 text-[#4E5968] hover:bg-[#F2F4F6]"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {/* Overlay + drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/30 md:hidden"
            onClick={() => setOpen(false)}
          />
          <nav
            aria-label="모바일 내비게이션"
            className="fixed right-0 top-0 z-50 flex h-full w-72 flex-col bg-white shadow-xl md:hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[#F2F4F6] px-4 py-4">
              <div className="text-xs text-[#8B95A1]">
                {workspace.teamId} · <span className="font-medium text-[#4E5968]">{workspace.memberName}</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="메뉴 닫기"
                className="rounded-lg p-1 text-[#8B95A1] hover:bg-[#F2F4F6]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Links */}
            <div className="flex-1 overflow-y-auto px-2 py-3">
              {nav.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-medium",
                      active
                        ? "bg-[#EBF3FF] text-[#3182F6]"
                        : "text-[#4E5968] hover:bg-[#F2F4F6]",
                    )}
                  >
                    <Icon className={cn("h-[18px] w-[18px]", active ? "text-[#3182F6]" : "text-[#B0B8C1]")} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* Logout */}
            <div className="border-t border-[#F2F4F6] px-2 py-3">
              <button
                onClick={logout}
                disabled={busy}
                aria-busy={busy}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-[#B0B8C1] hover:bg-[#F2F4F6] hover:text-[#4E5968] disabled:opacity-40"
              >
                <LogOut className="h-[18px] w-[18px]" />
                <span>로그아웃</span>
              </button>
            </div>
          </nav>
        </>
      )}
    </>
  );
}
