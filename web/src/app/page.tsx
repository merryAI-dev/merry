import { redirect } from "next/navigation";
import { Shield } from "lucide-react";

import { LoginPanel } from "@/components/LoginPanel";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function Home({
  searchParams,
}: {
  searchParams?:
    | Record<string, string | string[] | undefined>
    | Promise<Record<string, string | string[] | undefined>>;
}) {
  const ws = await getWorkspaceFromCookies();
  if (ws) redirect("/hub");

  const sp = await Promise.resolve(searchParams ?? {});
  const errorCode = typeof sp.error === "string" ? sp.error : "";
  const googleEnabled = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
  return (
    <div className="min-h-screen px-4 py-10">
      <div className="mx-auto grid max-w-5xl items-center gap-10 md:grid-cols-2 md:gap-12">
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1.5 text-xs font-medium text-[color:var(--ink)] ring-1 ring-[color:var(--line)]">
            <Shield className="h-4 w-4 text-[color:var(--accent)]" />
            서버 측 저장 + 협업 히스토리
          </div>
          <h1 className="mt-4 font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight text-[color:var(--ink)] md:text-5xl">
            투자 분석을{" "}
            <span className="text-[color:var(--accent)]">협업 문서</span>로
          </h1>
          <p className="mt-4 max-w-xl text-base leading-7 text-[color:var(--muted)]">
            Merry는 팀 과업, 서류, 일정, 코멘트와 함께 투자심사 보고서 초안을
            만들고, 커서처럼 특정 문장에 피드백을 남겨서 수정본을 생성할 수 있게
            합니다.
          </p>
          <div className="mt-7 grid max-w-xl grid-cols-2 gap-3 text-sm">
            <div className="m-card rounded-2xl p-4">
              <div className="font-medium text-[color:var(--ink)]">협업 허브</div>
              <div className="mt-1 text-[color:var(--muted)]">
                보드, 체크리스트, 캘린더, 피드
              </div>
            </div>
            <div className="m-card rounded-2xl p-4">
              <div className="font-medium text-[color:var(--ink)]">드래프트 리뷰</div>
              <div className="mt-1 text-[color:var(--muted)]">
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
