import { redirect } from "next/navigation";
import { Shield } from "lucide-react";

import { LoginPanel } from "@/components/LoginPanel";
import { SpaceBackground } from "@/components/SpaceBackground";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function Home({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const ws = await getWorkspaceFromCookies();
  if (ws) redirect("/hub");

  const sp = searchParams ? await searchParams : {};
  const errorCode = typeof sp.error === "string" ? sp.error : "";
  const googleEnabled = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

  return (
    <>
      <SpaceBackground />

      <div className="dark-landing flex min-h-screen items-center justify-center px-4 py-12 relative">
        <div className="mx-auto max-w-2xl w-full relative z-10 space-y-12">
          {/* Hero Content */}
          <div className="text-center space-y-8">
            <div className="inline-flex items-center gap-2 rounded-full bg-[color:var(--card)] backdrop-blur-md px-4 py-2 text-xs font-medium text-[color:var(--ink-light)] border border-[color:var(--accent-purple)]/30 shadow-[0_0_30px_rgba(30,64,175,0.15)]">
              <Shield className="h-4 w-4 text-[color:var(--accent-cyan)]" />
              서버 측 저장 + 협업 히스토리
            </div>

            <h1 className="font-[family-name:var(--font-display)] text-6xl md:text-7xl leading-tight tracking-tight text-white font-bold">
              투자 분석을 함께
            </h1>

            <div className="space-y-2">
              <p className="text-xl md:text-2xl text-[color:var(--ink-light)] font-light">
                <span className="gradient-text font-semibold">협업 문서</span>로 만드는
              </p>
              <p className="text-lg md:text-xl text-[color:var(--muted)]">
                Tokens / Equity
              </p>
            </div>

            <div className="flex items-center justify-center gap-4 pt-4">
              <div className="h-px w-16 bg-gradient-to-r from-transparent via-[color:var(--accent-cyan)] to-transparent"></div>
              <div className="h-2 w-2 rounded-full bg-[color:var(--accent-cyan)] shadow-[0_0_10px_rgba(14,165,233,0.8)]"></div>
              <div className="h-px w-16 bg-gradient-to-r from-transparent via-[color:var(--accent-cyan)] to-transparent"></div>
            </div>
          </div>

          {/* Login Panel */}
          <div className="max-w-md mx-auto">
            <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
          </div>

          {/* Features */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-center pt-8">
            <div className="p-4 rounded-xl bg-[color:var(--card)]/50 backdrop-blur-sm border border-[color:var(--card-border)]">
              <div className="text-2xl font-bold text-[color:var(--accent-cyan)] mb-1">팀 과업</div>
              <div className="text-sm text-[color:var(--muted)]">실시간 협업</div>
            </div>
            <div className="p-4 rounded-xl bg-[color:var(--card)]/50 backdrop-blur-sm border border-[color:var(--card-border)]">
              <div className="text-2xl font-bold text-[color:var(--accent-purple)] mb-1">서류 관리</div>
              <div className="text-sm text-[color:var(--muted)]">통합 문서함</div>
            </div>
            <div className="p-4 rounded-xl bg-[color:var(--card)]/50 backdrop-blur-sm border border-[color:var(--card-border)]">
              <div className="text-2xl font-bold text-[color:var(--accent-pink)] mb-1">일정 공유</div>
              <div className="text-sm text-[color:var(--muted)]">달력 연동</div>
            </div>
          </div>
        </div>

        {/* Ambient glow effects */}
        <div className="fixed inset-0 pointer-events-none -z-5">
          <div className="absolute top-20 left-10 w-96 h-96 bg-[color:var(--accent-purple)] rounded-full opacity-20 blur-[120px]"></div>
          <div className="absolute bottom-20 right-10 w-96 h-96 bg-[color:var(--accent-cyan)] rounded-full opacity-20 blur-[120px]"></div>
        </div>
      </div>
    </>
  );
}
