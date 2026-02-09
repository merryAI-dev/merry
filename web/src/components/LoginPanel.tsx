"use client";

import * as React from "react";
import { ArrowRight, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

const TEAM_OPTIONS = [
  { label: "Team 1", value: "team_1" },
  { label: "Team 2", value: "team_2" },
  { label: "Team 3", value: "team_3" },
  { label: "Team 4", value: "team_4" },
];

function prettyError(code: string): string | null {
  if (!code) return null;
  if (code === "AccessDenied") return "@mysc.co.kr 계정만 허용됩니다.";
  if (code === "OAuthSignin") return "Google 로그인 설정을 확인하세요.";
  if (code === "OAuthCallback") return "로그인 콜백 처리에 실패했습니다. 잠시 후 다시 시도하세요.";
  if (code === "Configuration") return "로그인 설정이 누락되었습니다. 환경변수를 확인하세요.";
  if (code === "UseGoogleButton") return "홈 화면에서 'Google로 로그인' 버튼을 눌러 로그인하세요.";
  return "로그인에 실패했습니다.";
}

export function LoginPanel({
  googleEnabled,
  errorCode,
}: {
  googleEnabled: boolean;
  errorCode?: string;
}) {
  const router = useRouter();
  const [teamId, setTeamId] = React.useState("team_1");
  const [memberName, setMemberName] = React.useState("");
  const [passcode, setPasscode] = React.useState("");
  const [error, setError] = React.useState<string | null>(prettyError(errorCode ?? ""));
  const [busy, setBusy] = React.useState(false);

  async function loginWithPasscode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/workspace", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ teamId, memberName, passcode }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok || !json?.ok) {
        const msg = googleEnabled
          ? "Google 로그인이 활성화되어 팀 코드 로그인은 비활성화되었습니다."
          : "팀 코드가 올바르지 않거나 입력값이 부족합니다.";
        setError(msg);
        return;
      }
      router.replace("/hub");
    } catch {
      setError("로그인 요청에 실패했습니다. 네트워크/서버 설정을 확인하세요.");
    } finally {
      setBusy(false);
    }
  }

  function loginWithGoogle() {
    signIn("google", { callbackUrl: "/hub" });
  }

  return (
    <Card variant="strong" className="p-6 md:p-7 relative overflow-hidden">
      {/* Card gradient accent */}
      <div className="absolute -top-20 -right-20 w-40 h-40 bg-[color:var(--accent-purple)] rounded-full opacity-10 blur-[80px]"></div>

      <div className="relative z-10">
        <div className="text-sm font-semibold text-[color:var(--ink)]">워크스페이스 로그인</div>
        <div className="mt-1.5 text-sm text-[color:var(--muted)] leading-relaxed">
          {googleEnabled
            ? "회사 Google 계정으로 로그인합니다. (@mysc.co.kr만 허용)"
            : "현재는 팀 코드 로그인(레거시)만 활성화되어 있습니다."}
        </div>

        <div className="mt-6 space-y-3">
          {googleEnabled ? (
            <>
              <div className="inline-flex items-center gap-2 rounded-2xl bg-[color:var(--card)]/80 backdrop-blur-md px-3 py-2 text-xs font-medium text-[color:var(--ink)] border border-[color:var(--accent-purple)]/30">
                <Shield className="h-4 w-4 text-[color:var(--accent-purple)]" />
                도메인 제한: <span className="font-mono text-[color:var(--accent-cyan)]">@mysc.co.kr</span>
              </div>
              <Button variant="primary" className="w-full" onClick={loginWithGoogle}>
                Google로 로그인 <ArrowRight className="h-4 w-4" />
              </Button>
            </>
          ) : (
            <form className="space-y-3" onSubmit={loginWithPasscode}>
              <label className="block">
                <div className="mb-1.5 text-xs font-medium text-[color:var(--muted)]">팀</div>
                <select
                  className="h-11 w-full rounded-xl border border-[color:var(--line)] bg-[color:var(--card)]/60 backdrop-blur-md px-3 text-sm text-[color:var(--ink)] outline-none transition-all duration-300 focus:border-[color:var(--accent-purple)]/60 focus:bg-[color:var(--card)]/80 focus:shadow-[0_0_20px_rgba(30,64,175,0.15)] hover:border-[color:var(--accent-purple)]/40"
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                >
                  {TEAM_OPTIONS.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <div className="mb-1.5 text-xs font-medium text-[color:var(--muted)]">닉네임</div>
                <Input
                  value={memberName}
                  onChange={(e) => setMemberName(e.target.value)}
                  placeholder="이름 또는 닉네임"
                  autoComplete="name"
                />
              </label>

              <label className="block">
                <div className="mb-1.5 text-xs font-medium text-[color:var(--muted)]">팀 코드</div>
                <Input
                  value={passcode}
                  onChange={(e) => setPasscode(e.target.value)}
                  placeholder="워크스페이스 코드"
                  type="password"
                  autoComplete="current-password"
                />
              </label>

              <Button
                variant="primary"
                className="w-full mt-4"
                disabled={busy || !memberName || !passcode}
                type="submit"
              >
                워크스페이스 들어가기 <ArrowRight className="h-4 w-4" />
              </Button>
            </form>
          )}

          {error ? (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 backdrop-blur-sm px-3 py-2.5 text-sm text-rose-300">
              {error}
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
