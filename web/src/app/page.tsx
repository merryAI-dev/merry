import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { LoginPanel } from "@/components/LoginPanel";
import { HeroIllustration } from "@/components/icons/HeroIllustration";
import { IconChart } from "@/components/icons/IconChart";
import { IconFolder } from "@/components/icons/IconFolder";
import { IconTeam } from "@/components/icons/IconTeam";
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
    <div className="min-h-screen bg-[#F2F4F6]">
      {/* ── Header ── */}
      <header className="flex items-center px-6 py-5">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-[#3182F6] flex items-center justify-center shadow-sm">
            <span className="text-white font-black text-sm leading-none">M</span>
          </div>
          <span
            className="font-bold text-[#191F28] text-lg tracking-tight"
            style={{ fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)" }}
          >
            Merry
          </span>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="flex flex-col items-center px-6 pt-2 pb-20">
        {/* Hero Illustration */}
        <HeroIllustration className="w-full max-w-[480px] h-auto" />

        {/* Hero Text */}
        <div className="text-center mt-6 mb-10">
          <h1
            className="text-[50px] font-black text-[#191F28] leading-[1.15] tracking-[-0.03em] mb-3"
            style={{ fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)" }}
          >
            투자 분석을<br />한 단계 더
          </h1>
          <p
            className="text-[#8B95A1] text-lg"
            style={{ fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)" }}
          >
            VC 심사역을 위한 협업 분석 워크스페이스
          </p>
        </div>

        {/* Login Panel */}
        <div className="w-full max-w-sm">
          <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
        </div>

        {/* Feature Cards */}
        <div className="mt-12 grid grid-cols-3 gap-3 w-full max-w-sm">
          <FeatureCard icon={<IconChart className="w-9 h-9" />} title="투자 분석" subtitle="AI 심사" />
          <FeatureCard icon={<IconFolder className="w-9 h-9" />} title="서류 관리" subtitle="문서함" />
          <FeatureCard icon={<IconTeam className="w-9 h-9" />} title="팀 협업" subtitle="실시간" />
        </div>
      </main>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  subtitle,
}: {
  icon: ReactNode;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="bg-white rounded-2xl p-4 flex flex-col items-center gap-2.5 shadow-[0_2px_12px_rgba(0,0,0,0.06)]">
      {icon}
      <div className="text-center">
        <div
          className="text-[13px] font-semibold text-[#191F28]"
          style={{ fontFamily: "var(--font-korean, system-ui)" }}
        >
          {title}
        </div>
        <div
          className="text-[11px] text-[#8B95A1] mt-0.5"
          style={{ fontFamily: "var(--font-korean, system-ui)" }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
}
