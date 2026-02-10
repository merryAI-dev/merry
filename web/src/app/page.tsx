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
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      {/* Ambient light effects */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-20 left-10 w-96 h-96 bg-[color:var(--accent-purple)] rounded-full opacity-10 blur-[120px]"></div>
        <div className="absolute bottom-20 right-10 w-96 h-96 bg-[color:var(--accent-cyan)] rounded-full opacity-10 blur-[120px]"></div>
      </div>

      <div className="mx-auto max-w-md w-full relative z-10 space-y-8">
        <div className="text-center">
          <div className="inline-flex items-center gap-2 rounded-full bg-[color:var(--card)]/80 backdrop-blur-md px-3 py-1.5 text-xs font-medium text-[color:var(--ink)] border border-[color:var(--accent-purple)]/30 shadow-[0_0_20px_rgba(30,64,175,0.15)]">
            <Shield className="h-4 w-4 text-[color:var(--accent-purple)]" />
            서버 측 저장 + 협업 히스토리
          </div>
          <h1 className="mt-6 font-[family-name:var(--font-display)] text-4xl leading-tight tracking-tight text-[color:var(--ink)]">
            투자 분석을{" "}
            <span className="gradient-text font-bold">협업 문서</span>로
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-[color:var(--muted)]">
            팀 과업, 서류, 일정과 함께<br />투자심사 보고서를 협업합니다
          </p>
        </div>

        <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
      </div>
    </div>
  );
}
