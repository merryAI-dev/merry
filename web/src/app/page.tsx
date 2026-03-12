import { redirect } from "next/navigation";
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
    <div
      className="relative min-h-screen overflow-hidden flex flex-col"
      style={{ background: "var(--bg)" }}
    >
      {/* ── Ambient orbs ── */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        {/* Top-left orb */}
        <div
          className="absolute -top-40 -left-40 w-[600px] h-[600px] rounded-full opacity-[0.12]"
          style={{
            background: "radial-gradient(circle, #7C3AED 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        {/* Bottom-right orb */}
        <div
          className="absolute -bottom-60 -right-20 w-[700px] h-[700px] rounded-full opacity-[0.08]"
          style={{
            background: "radial-gradient(circle, #14B8A6 0%, transparent 70%)",
            filter: "blur(80px)",
          }}
        />
        {/* Center subtle glow */}
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] opacity-[0.04]"
          style={{
            background: "radial-gradient(ellipse, #7C3AED 0%, transparent 60%)",
            filter: "blur(40px)",
          }}
        />
        {/* Fine grid overlay */}
        <div
          className="absolute inset-0 opacity-[0.025]"
          style={{
            backgroundImage: `
              linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
              linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
            `,
            backgroundSize: "60px 60px",
          }}
        />
      </div>

      {/* ── Header ── */}
      <header className="relative z-10 flex items-center justify-between px-8 py-6">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{
              background: "linear-gradient(135deg, #7C3AED, #5B21B6)",
              boxShadow: "0 0 20px rgba(124,58,237,0.4)",
            }}
          >
            <span className="text-white font-black text-sm leading-none">M</span>
          </div>
          <span
            className="font-bold text-lg tracking-tight"
            style={{ color: "var(--ink)", fontFamily: "var(--font-korean, var(--font-merry-sans))" }}
          >
            Merry
          </span>
        </div>

        <div
          className="text-xs font-medium px-3 py-1.5 rounded-full"
          style={{
            background: "rgba(124,58,237,0.1)",
            border: "1px solid rgba(124,58,237,0.2)",
            color: "#A78BFA",
          }}
        >
          MYSC AX
        </div>
      </header>

      {/* ── Main ── */}
      <main className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 py-12">
        {/* Hero */}
        <div className="text-center mb-12 max-w-lg">
          {/* Eyebrow */}
          <div
            className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.12em] uppercase mb-6 px-4 py-2 rounded-full"
            style={{
              background: "rgba(20,184,166,0.08)",
              border: "1px solid rgba(20,184,166,0.2)",
              color: "#2DD4BF",
            }}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "#2DD4BF", boxShadow: "0 0 6px #2DD4BF" }}
            />
            VC 투자 분석 워크스페이스
          </div>

          <h1
            className="text-[52px] font-black leading-[1.1] tracking-[-0.03em] mb-4"
            style={{
              fontFamily: "var(--font-merry-display, var(--font-korean))",
              color: "var(--ink)",
            }}
          >
            투자 분석을{" "}
            <span
              style={{
                background: "linear-gradient(135deg, #A78BFA 0%, #7C3AED 50%, #14B8A6 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              함께
            </span>
          </h1>

          <p
            className="text-base leading-relaxed"
            style={{ color: "var(--ink-light)", fontFamily: "var(--font-korean, system-ui)" }}
          >
            심사역과 AI가 함께 만드는 협업 분석 워크스페이스
          </p>
        </div>

        {/* Login card */}
        <div className="w-full max-w-sm">
          <LoginPanel googleEnabled={googleEnabled} errorCode={errorCode} />
        </div>

        {/* Feature chips */}
        <div className="mt-10 flex items-center gap-3 flex-wrap justify-center">
          {[
            { label: "투자 분석 AI", color: "#A78BFA" },
            { label: "서류 자동화", color: "#2DD4BF" },
            { label: "팀 협업", color: "#FB7185" },
            { label: "Exit 프로젝션", color: "#FCD34D" },
          ].map(({ label, color }) => (
            <div
              key={label}
              className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full"
              style={{
                background: "rgba(255,255,255,0.04)",
                border: "1px solid rgba(255,255,255,0.08)",
                color: "var(--ink-light)",
              }}
            >
              <span
                className="w-1.5 h-1.5 rounded-full"
                style={{ background: color }}
              />
              {label}
            </div>
          ))}
        </div>
      </main>

      {/* ── Footer ── */}
      <footer className="relative z-10 text-center pb-6">
        <p className="text-xs" style={{ color: "var(--muted)" }}>
          © 2025 MYSC · Merry AX Platform
        </p>
      </footer>
    </div>
  );
}
