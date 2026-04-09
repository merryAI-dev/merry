import { redirect } from "next/navigation";
import { LoginPanel } from "@/components/LoginPanel";
import { DEFAULT_AFTER_LOGIN_PATH } from "@/lib/products";
import { getWorkspaceFromCookies } from "@/lib/workspaceServer";

export default async function Home({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const ws = await getWorkspaceFromCookies();
  if (ws) redirect(DEFAULT_AFTER_LOGIN_PATH);

  const sp = searchParams ? await searchParams : {};
  const errorCode = typeof sp.error === "string" ? sp.error : "";
  const googleEnabled = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);

  return (
    <div
      className="relative min-h-screen flex flex-col"
      style={{ background: "#FFFFFF" }}
    >
      {/* ── Header ── */}
      <header className="relative z-10 flex items-center justify-between px-8 py-5">
        <div className="flex items-center gap-2.5">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "#00C805" }}
          >
            <span className="text-white font-black text-sm leading-none">M</span>
          </div>
          <span
            className="font-bold text-lg tracking-tight"
            style={{
              color: "#1A1D21",
              fontFamily: "var(--font-korean, var(--font-merry-sans))",
            }}
          >
            Merry
          </span>
        </div>
      </header>

      {/* ── Main ── */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 pb-20">
        {/* Hero */}
        <div className="text-center mb-10 max-w-xl">
          <h1
            className="text-[56px] font-black leading-[1.08] tracking-[-0.035em] mb-5"
            style={{
              fontFamily: "var(--font-merry-display, var(--font-korean))",
              color: "#1A1D21",
            }}
          >
            투자 분석을{" "}
            <span style={{ color: "#00C805" }}>
              함께
            </span>
          </h1>

          <p
            className="text-lg leading-relaxed"
            style={{
              color: "#6F7780",
              fontFamily: "var(--font-korean, system-ui)",
            }}
          >
            AI 심사역 동료 메리와 함께 하는 투자 여정
          </p>
        </div>

        {/* Login card */}
        <div className="w-full max-w-sm">
          <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
        </div>

        {/* Feature chips */}
        <div className="mt-10 flex items-center gap-2.5 flex-wrap justify-center">
          {[
            { label: "투자 분석 AI", dot: "#00C805" },
            { label: "서류 자동화", dot: "#3B82F6" },
            { label: "팀 협업", dot: "#F59E0B" },
            { label: "Exit 프로젝션", dot: "#8B5CF6" },
          ].map(({ label, dot }) => (
            <div
              key={label}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full"
              style={{
                background: "#F7F8F9",
                border: "1px solid #E3E5E8",
                color: "#6F7780",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: dot }}
              />
              {label}
            </div>
          ))}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="relative z-10 text-center pb-6">
        <p className="text-xs" style={{ color: "#9DA5AE" }}>
          © 2025 MYSC · Merry AX Platform
        </p>
      </footer>
    </div>
  );
}
