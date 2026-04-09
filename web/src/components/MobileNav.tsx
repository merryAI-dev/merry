"use client";

import * as React from "react";
import {
  AlertTriangle,
  Menu,
  X,
  ClipboardList,
  FileSpreadsheet,
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
  { href: "/hub",             label: "협업 허브",      icon: LayoutDashboard },
  { href: "/analysis",        label: "분석",           icon: UploadCloud },
  { href: "/review",          label: "투자심사",       icon: ClipboardList },
  { href: "/funds",           label: "펀드",           icon: LineChart },
  { href: "/exit-projection", label: "Exit 프로젝션",  icon: TrendingUp },
  { href: "/check",           label: "조건 검사",      icon: ScanSearch },
  { href: "/documents",       label: "문서 추출",      icon: Files },
  { href: "/extract",         label: "재무 일괄 추출", icon: FileSpreadsheet },
  { href: "/drafts",          label: "드래프트",       icon: FileText },
  { href: "/review/queue",    label: "검토 큐",        icon: AlertTriangle },
  { href: "/history",         label: "작업 이력",      icon: History },
  { href: "/playground",      label: "플레이그라운드", icon: FlaskConical },
  { href: "/admin",           label: "관리자",         icon: Settings },
];

export function MobileNav({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

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
      <header
        className="sticky top-0 z-40 flex items-center justify-between px-4 py-3 md:hidden"
        style={{
          background: "var(--sidebar-bg)",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg"
            style={{ background: "linear-gradient(135deg, #7C3AED, #6D28D9)" }}
          >
            <span className="text-xs font-black text-white">M</span>
          </div>
          <span className="text-[15px] font-bold tracking-tight" style={{ color: "var(--ink)" }}>
            Merry
          </span>
        </div>
        <button
          onClick={() => setOpen(!open)}
          aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
          aria-expanded={open}
          className="rounded-lg p-2 transition-colors"
          style={{ color: "var(--ink-light)" }}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {/* Overlay + drawer */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 md:hidden"
            style={{ background: "rgba(0,0,0,0.7)" }}
            onClick={() => setOpen(false)}
          />
          <nav
            aria-label="모바일 내비게이션"
            className="fixed right-0 top-0 z-50 flex h-full w-72 flex-col md:hidden"
            style={{
              background: "var(--sidebar-bg)",
              boxShadow: "-8px 0 40px rgba(0,0,0,0.6)",
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-4 py-4"
              style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
            >
              <div className="text-xs" style={{ color: "var(--muted)" }}>
                {workspace.teamId} ·{" "}
                <span className="font-medium" style={{ color: "var(--ink-light)" }}>
                  {workspace.memberName}
                </span>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="메뉴 닫기"
                className="rounded-lg p-1 transition-colors"
                style={{ color: "var(--muted)" }}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Links */}
            <div className="flex-1 overflow-y-auto px-2 py-3 flex flex-col gap-0.5">
              {nav.map((item) => {
                const Icon = item.icon;
                const active = item.href === "/review"
                  ? pathname === "/review"
                    || (pathname.startsWith("/review/") && !pathname.startsWith("/review/queue"))
                  : pathname === item.href || pathname.startsWith(item.href + "/");
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-150",
                    )}
                    style={
                      active
                        ? { background: "rgba(124,58,237,0.15)", color: "#A78BFA" }
                        : { color: "var(--ink-light)" }
                    }
                  >
                    <Icon
                      className="h-[17px] w-[17px] shrink-0"
                      style={{ color: active ? "#A78BFA" : "var(--muted)" }}
                    />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>

            {/* Logout */}
            <div
              className="px-2 py-3"
              style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
            >
              <button
                onClick={logout}
                disabled={busy}
                aria-busy={busy}
                className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-150 disabled:opacity-40"
                style={{ color: "var(--muted)" }}
              >
                <LogOut className="h-[17px] w-[17px]" />
                <span>로그아웃</span>
              </button>
            </div>
          </nav>
        </>
      )}
    </>
  );
}
