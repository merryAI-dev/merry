import { redirect } from "next/navigation";
import { Shield } from "lucide-react";

import { LoginPanel } from "@/components/LoginPanel";
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
    <div className="min-h-screen px-4 py-10 relative">
      {/* Ambient light effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-20 left-10 w-96 h-96 bg-[color:var(--accent-purple)] rounded-full opacity-10 blur-[120px]"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-[color:var(--accent-cyan)] rounded-full opacity-10 blur-[120px]"></div>
      </div>

      <div className="mx-auto grid max-w-5xl items-center gap-10 md:grid-cols-2 md:gap-12 relative z-10">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-[color:var(--card)]/80 backdrop-blur-md px-3 py-1.5 text-xs font-medium text-[color:var(--ink)] border border-[color:var(--accent-purple)]/30 shadow-[0_0_20px_rgba(168,85,247,0.15)]">
            <Shield className="h-4 w-4 text-[color:var(--accent-purple)]" />
            서버 측 저장 + 협업 히스토리
          </div>
          <h1 className="mt-6 font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight text-[color:var(--ink)] md:text-5xl">
            투자 분석을{" "}
            <span className="gradient-text font-bold">협업 문서</span>로
          </h1>
          <p className="mt-5 max-w-xl text-base leading-7 text-[color:var(--muted)]">
            Merry는 팀 과업, 서류, 일정, 코멘트와 함께 투자심사 보고서 초안을
            만들고, 커서처럼 특정 문장에 피드백을 남겨서 수정본을 생성할 수 있게
            합니다.
          </p>
          <div className="mt-8 grid max-w-xl grid-cols-2 gap-3 text-sm">
            <div className="m-card rounded-2xl p-5 hover:scale-[1.02] transition-transform">
              <div className="font-semibold text-[color:var(--ink)]">협업 허브</div>
              <div className="mt-1.5 text-[color:var(--muted)] leading-relaxed">
                보드, 체크리스트, 캘린더, 피드
              </div>
            </div>
            <div className="m-card rounded-2xl p-5 hover:scale-[1.02] transition-transform">
              <div className="font-semibold text-[color:var(--ink)]">드래프트 리뷰</div>
              <div className="mt-1.5 text-[color:var(--muted)] leading-relaxed">
                선택 영역 코멘트 + 반영/거절
              </div>
            </div>
          </div>
        </div>

        <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
      </div>
    </div>
  );
}
