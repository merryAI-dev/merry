"use client";

import * as React from "react";
import { ChevronLeft, ChevronRight, LogOut } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { cn } from "@/lib/cn";
import { requestLogout } from "@/lib/logoutClient";
import type { WorkspaceSession } from "@/lib/workspace";

import { REVIEW_NAV_ITEMS } from "./nav";

const STORAGE_KEY = "merry-review-sidebar-collapsed";

export function ReviewSidebar({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = React.useState(false);
  const [collapsed, setCollapsed] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

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
    setError(null);
    try {
      const result = await requestLogout();
      if (result.ok) {
        router.replace("/");
      } else {
        setError(result.error);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside
      className={cn(
        "sticky top-3 h-[calc(100vh-1.5rem)] shrink-0 transition-all duration-300 ease-in-out",
        collapsed ? "w-[72px]" : "w-64",
      )}
    >
      <div
        className="relative flex h-full flex-col overflow-hidden"
        style={{
          background: "linear-gradient(180deg, #12182A 0%, #0C1020 100%)",
          borderRight: "1px solid rgba(167, 139, 250, 0.12)",
          borderRadius: "18px",
          boxShadow: "0 24px 60px rgba(7, 10, 24, 0.42)",
        }}
      >
        <button
          onClick={toggle}
          className="absolute -right-3 top-6 z-20 flex h-6 w-6 items-center justify-center rounded-full border transition-all duration-150"
          style={{
            background: "#12182A",
            borderColor: "rgba(167, 139, 250, 0.22)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.4)",
          }}
          aria-label={collapsed ? "검토 사이드바 열기" : "검토 사이드바 접기"}
        >
          {collapsed ? (
            <ChevronRight className="h-3.5 w-3.5 text-[#C4B5FD]" />
          ) : (
            <ChevronLeft className="h-3.5 w-3.5 text-[#C4B5FD]" />
          )}
        </button>

        <div
          className={cn("px-4 pb-4 pt-5", collapsed && "flex flex-col items-center px-2")}
          style={{ borderBottom: "1px solid rgba(167, 139, 250, 0.1)" }}
        >
          {collapsed ? (
            <div
              className="flex h-9 w-9 items-center justify-center rounded-2xl"
              style={{ background: "linear-gradient(135deg, #8B5CF6, #4F46E5)" }}
            >
              <span className="text-sm font-black text-white">R</span>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-3">
                <div
                  className="flex h-9 w-9 items-center justify-center rounded-2xl"
                  style={{ background: "linear-gradient(135deg, #8B5CF6, #4F46E5)" }}
                >
                  <span className="text-sm font-black text-white">R</span>
                </div>
                <div>
                  <div className="text-[14px] font-semibold uppercase tracking-[0.22em] text-[#A5B4FC]">
                    Review
                  </div>
                  <div className="text-[17px] font-black tracking-tight text-white">
                    투자심사 워크벤치
                  </div>
                </div>
              </div>
              <div className="mt-3 text-[11px] leading-snug text-[#94A3B8]">
                {workspace.teamId} · <span className="font-medium text-[#E2E8F0]">{workspace.memberName}</span>
              </div>
            </>
          )}
        </div>

        <nav
          aria-label="투자심사 내비게이션"
          className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3"
        >
          {REVIEW_NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                title={collapsed ? item.label : undefined}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative flex items-center rounded-2xl text-[13px] font-medium transition-all duration-150",
                  collapsed ? "justify-center px-0 py-3" : "gap-3 px-3 py-2.5",
                )}
                style={
                  active
                    ? {
                        background: "rgba(139, 92, 246, 0.16)",
                        color: "#DDD6FE",
                      }
                    : { color: "#CBD5E1" }
                }
              >
                {!collapsed && (
                  <span
                    className={cn(
                      "absolute left-0 top-2 bottom-2 w-[3px] rounded-full transition-all duration-150",
                      active ? "opacity-100" : "opacity-0 group-hover:opacity-40",
                    )}
                    style={{ background: "linear-gradient(180deg, #8B5CF6, #6366F1)" }}
                  />
                )}
                <Icon
                  className="h-[17px] w-[17px] shrink-0"
                  style={{ color: active ? "#C4B5FD" : "#94A3B8" }}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <div className="px-2 pb-3 pt-2" style={{ borderTop: "1px solid rgba(167, 139, 250, 0.1)" }}>
          {!collapsed && error && (
            <p className="px-3 pb-2 text-[11px] leading-5 text-[#FCA5A5]" role="alert">
              {error}
            </p>
          )}
          <button
            onClick={logout}
            disabled={busy}
            aria-busy={busy}
            title={collapsed ? "로그아웃" : undefined}
            className={cn(
              "flex w-full items-center rounded-2xl text-[13px] font-medium transition-all duration-150 disabled:opacity-40",
              collapsed ? "justify-center py-3" : "gap-3 px-3 py-2.5",
            )}
            style={{ color: "#94A3B8" }}
          >
            <LogOut className="h-[17px] w-[17px]" />
            {!collapsed && <span>로그아웃</span>}
          </button>
        </div>
      </div>
    </aside>
  );
}
