"use client";

import * as React from "react";
import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Files,
  LogOut,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/cn";
import type { WorkspaceSession } from "@/lib/workspace";

const nav = [
  { href: "/report",          label: "투자심사",       icon: ClipboardList,   group: "main" },
  { href: "/documents",       label: "문서 추출",      icon: Files,           group: "main" },
  { href: "/admin",           label: "관리자",         icon: Settings,        group: "dev" },
];

const groupLabels: Record<string, string> = {
  main: "메인",
  tools: "도구",
  manage: "관리",
  dev: "개발",
};

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

  const groups = ["main", "tools", "manage", "dev"];

  return (
    <aside
      className={cn(
        "sticky top-3 h-[calc(100vh-1.5rem)] shrink-0 transition-all duration-300 ease-in-out",
        collapsed ? "w-[68px]" : "w-60",
      )}
    >
      <div
        className="flex h-full flex-col relative overflow-hidden"
        style={{
          background: "var(--sidebar-bg)",
          borderRight: "1px solid rgba(255,255,255,0.05)",
          borderRadius: "16px",
        }}
      >
        {/* Toggle button */}
        <button
          onClick={toggle}
          className="absolute -right-3 top-6 z-20 flex h-6 w-6 items-center justify-center rounded-full border transition-all duration-150"
          style={{
            background: "var(--bg-elevated)",
            borderColor: "var(--card-border)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
          }}
          aria-label={collapsed ? "사이드바 열기" : "사이드바 접기"}
        >
          {collapsed
            ? <ChevronRight className="h-3.5 w-3.5" style={{ color: "var(--muted)" }} />
            : <ChevronLeft  className="h-3.5 w-3.5" style={{ color: "var(--muted)" }} />}
        </button>

        {/* Header */}
        <div
          className={cn(
            "px-4 pt-5 pb-4",
            collapsed && "flex flex-col items-center px-2",
          )}
          style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
        >
          {collapsed ? (
            <div
              className="w-8 h-8 rounded-xl flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, #7C3AED, #6D28D9)" }}
            >
              <span className="text-white font-black text-sm">M</span>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2.5">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: "linear-gradient(135deg, #7C3AED, #6D28D9)" }}
                >
                  <span className="text-white font-black text-xs">M</span>
                </div>
                <span
                  className="font-bold text-[15px] tracking-tight"
                  style={{ color: "var(--ink)" }}
                >
                  Merry
                </span>
              </div>
              <div className="mt-2.5 text-[11px] leading-snug" style={{ color: "var(--muted)" }}>
                {workspace.teamId} ·{" "}
                <span className="font-medium" style={{ color: "var(--ink-light)" }}>
                  {workspace.memberName}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Nav */}
        <nav
          aria-label="메인 내비게이션"
          className="flex-1 px-2 py-3 flex flex-col overflow-y-auto"
          style={{ gap: "1px" }}
        >
          {groups.map((group) => {
            const items = nav.filter((n) => n.group === group);
            return (
              <div key={group} className="mb-1">
                {/* Group label */}
                {!collapsed && (
                  <div
                    className="px-3 py-1 text-[10px] font-semibold tracking-widest uppercase"
                    style={{ color: "var(--muted)" }}
                  >
                    {groupLabels[group]}
                  </div>
                )}
                {items.map((item) => {
                  const Icon = item.icon;
                  const active = pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      title={collapsed ? item.label : undefined}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "group relative flex items-center rounded-xl text-[13px] font-medium",
                        "transition-all duration-150",
                        collapsed ? "justify-center px-0 py-2.5" : "gap-3 px-3 py-2",
                      )}
                      style={
                        active
                          ? {
                              background: "rgba(124, 58, 237, 0.15)",
                              color: "#A78BFA",
                            }
                          : {}
                      }
                      onMouseEnter={(e) => {
                        if (!active) {
                          (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.05)";
                          (e.currentTarget as HTMLElement).style.color = "var(--ink)";
                        }
                      }}
                      onMouseLeave={(e) => {
                        if (!active) {
                          (e.currentTarget as HTMLElement).style.background = "";
                          (e.currentTarget as HTMLElement).style.color = "";
                        }
                      }}
                    >
                      {/* Left border */}
                      {!collapsed && (
                        <span
                          className={cn(
                            "absolute left-0 top-1 bottom-1 w-[3px] rounded-full transition-all duration-150",
                            active ? "opacity-100" : "opacity-0 group-hover:opacity-40",
                          )}
                          style={{ background: "#7C3AED" }}
                        />
                      )}
                      <Icon
                        className="h-[17px] w-[17px] shrink-0 transition-colors duration-150"
                        style={{ color: active ? "#A78BFA" : "var(--muted)" }}
                      />
                      {!collapsed && (
                        <span style={{ color: active ? "#A78BFA" : "var(--ink-light)" }}>
                          {item.label}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            );
          })}
        </nav>

        {/* Logout */}
        <div
          className="px-2 pb-3 pt-2"
          style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
        >
          <button
            onClick={logout}
            disabled={busy}
            aria-busy={busy}
            title={collapsed ? "로그아웃" : undefined}
            className={cn(
              "group relative flex w-full items-center rounded-xl text-[13px] font-medium",
              "transition-all duration-150 disabled:opacity-40",
              collapsed ? "justify-center py-2.5" : "gap-3 px-3 py-2",
            )}
            style={{ color: "var(--muted)" }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = "rgba(255,255,255,0.05)";
              (e.currentTarget as HTMLElement).style.color = "var(--ink-light)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = "";
              (e.currentTarget as HTMLElement).style.color = "var(--muted)";
            }}
          >
            {!collapsed && (
              <span
                className="absolute left-0 top-1 bottom-1 w-[3px] rounded-full opacity-0 group-hover:opacity-40 transition-all duration-150"
                style={{ background: "#F43F5E" }}
              />
            )}
            <LogOut className="h-[17px] w-[17px] shrink-0" />
            {!collapsed && <span>로그아웃</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}
