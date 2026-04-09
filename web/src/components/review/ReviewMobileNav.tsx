"use client";

import * as React from "react";
import { LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { requestLogout } from "@/lib/logoutClient";
import type { WorkspaceSession } from "@/lib/workspace";

import { REVIEW_NAV_ITEMS } from "./nav";

export function ReviewMobileNav({ workspace }: { workspace: WorkspaceSession }) {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    setOpen(false);
    setError(null);
  }, [pathname]);

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
    <>
      <header
        className="sticky top-0 z-40 flex items-center justify-between px-4 py-3 md:hidden"
        style={{
          background: "rgba(12, 16, 32, 0.94)",
          borderBottom: "1px solid rgba(167, 139, 250, 0.16)",
          backdropFilter: "blur(18px)",
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="flex h-8 w-8 items-center justify-center rounded-xl"
            style={{ background: "linear-gradient(135deg, #8B5CF6, #4F46E5)" }}
          >
            <span className="text-xs font-black text-white">R</span>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#A5B4FC]">
              Review
            </div>
            <div className="text-[15px] font-bold tracking-tight text-white">투자심사</div>
          </div>
        </div>
        <button
          onClick={() => setOpen((prev) => !prev)}
          aria-label={open ? "메뉴 닫기" : "메뉴 열기"}
          aria-expanded={open}
          className="rounded-xl p-2 text-[#E2E8F0]"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-[rgba(2,6,23,0.64)] md:hidden"
            onClick={() => setOpen(false)}
          />
          <nav
            aria-label="투자심사 모바일 내비게이션"
            className="fixed right-0 top-0 z-50 flex h-full w-72 flex-col md:hidden"
            style={{
              background: "linear-gradient(180deg, #12182A 0%, #0C1020 100%)",
              boxShadow: "-8px 0 40px rgba(0,0,0,0.45)",
            }}
          >
            <div
              className="flex items-center justify-between px-4 py-4"
              style={{ borderBottom: "1px solid rgba(167, 139, 250, 0.12)" }}
            >
              <div className="text-xs text-[#94A3B8]">
                {workspace.teamId} · <span className="font-medium text-[#E2E8F0]">{workspace.memberName}</span>
              </div>
              <button onClick={() => setOpen(false)} aria-label="메뉴 닫기" className="rounded-lg p-1 text-[#94A3B8]">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-3">
              {REVIEW_NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = item.match(pathname);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className="flex items-center gap-3 rounded-2xl px-3 py-3 text-[13px] font-medium transition-all duration-150"
                    style={
                      active
                        ? { background: "rgba(139, 92, 246, 0.16)", color: "#DDD6FE" }
                        : { color: "#CBD5E1" }
                    }
                  >
                    <Icon className="h-[17px] w-[17px]" style={{ color: active ? "#C4B5FD" : "#94A3B8" }} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>

            <div className="px-2 py-3" style={{ borderTop: "1px solid rgba(167, 139, 250, 0.12)" }}>
              {error && (
                <p className="px-3 pb-2 text-[11px] leading-5 text-[#FCA5A5]" role="alert">
                  {error}
                </p>
              )}
              <button
                onClick={logout}
                disabled={busy}
                aria-busy={busy}
                className="flex w-full items-center gap-3 rounded-2xl px-3 py-3 text-[13px] font-medium text-[#94A3B8] transition-all duration-150 disabled:opacity-40"
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
