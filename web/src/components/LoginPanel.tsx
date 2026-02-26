"use client";

import * as React from "react";
import { ArrowRight } from "lucide-react";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";

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

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <path d="M17.64 9.205c0-.639-.057-1.252-.164-1.841H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#fff" fillOpacity=".9"/>
      <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#fff" fillOpacity=".75"/>
      <path d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z" fill="#fff" fillOpacity=".6"/>
      <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z" fill="#fff" fillOpacity=".85"/>
    </svg>
  );
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
        setError("팀 코드가 올바르지 않거나 입력값이 부족합니다.");
        return;
      }
      router.replace("/hub");
    } catch {
      setError("로그인 요청에 실패했습니다.");
    } finally {
      setBusy(false);
    }
  }

  function loginWithGoogle() {
    signIn("google", { callbackUrl: "/hub" });
  }

  const fontStyle = { fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)" };

  return (
    <div
      className="w-full bg-white rounded-3xl shadow-[0_4px_24px_rgba(0,0,0,0.08)] p-6"
      style={fontStyle}
    >
      {/* Header */}
      <p className="text-[15px] font-semibold text-[#191F28] mb-1">워크스페이스 로그인</p>
      <p className="text-[13px] text-[#B0B8C1] mb-5">
        {googleEnabled ? "@mysc.co.kr 계정 전용" : "팀 코드로 로그인"}
      </p>

      {googleEnabled ? (
        <button
          onClick={loginWithGoogle}
          className="w-full h-[54px] bg-[#3182F6] hover:bg-[#1B6AE4] active:bg-[#1460CC] text-white rounded-2xl font-semibold text-[15px] flex items-center justify-center gap-2.5 transition-colors duration-150 shadow-[0_2px_12px_rgba(49,130,246,0.3)]"
          style={fontStyle}
        >
          <GoogleIcon />
          Google로 계속하기
        </button>
      ) : (
        <form className="space-y-3" onSubmit={loginWithPasscode}>
          <div>
            <label className="block text-[12px] font-medium text-[#8B95A1] mb-1.5">팀</label>
            <select
              className="w-full h-12 rounded-xl border border-[#E5E8EB] bg-white px-3 text-[14px] text-[#191F28] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20 transition-all"
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              style={fontStyle}
            >
              {TEAM_OPTIONS.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#8B95A1] mb-1.5">닉네임</label>
            <input
              className="w-full h-12 rounded-xl border border-[#E5E8EB] bg-white px-3 text-[14px] text-[#191F28] placeholder:text-[#C7CDD3] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20 transition-all"
              value={memberName}
              onChange={(e) => setMemberName(e.target.value)}
              placeholder="이름 또는 닉네임"
              autoComplete="name"
              style={fontStyle}
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#8B95A1] mb-1.5">팀 코드</label>
            <input
              className="w-full h-12 rounded-xl border border-[#E5E8EB] bg-white px-3 text-[14px] text-[#191F28] placeholder:text-[#C7CDD3] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20 transition-all"
              value={passcode}
              onChange={(e) => setPasscode(e.target.value)}
              placeholder="워크스페이스 코드"
              type="password"
              autoComplete="current-password"
              style={fontStyle}
            />
          </div>

          <button
            type="submit"
            disabled={busy || !memberName || !passcode}
            className="w-full h-[54px] mt-2 bg-[#3182F6] hover:bg-[#1B6AE4] active:bg-[#1460CC] disabled:opacity-40 disabled:pointer-events-none text-white rounded-2xl font-semibold text-[15px] flex items-center justify-center gap-2 transition-colors duration-150 shadow-[0_2px_12px_rgba(49,130,246,0.25)]"
            style={fontStyle}
          >
            워크스페이스 들어가기
            <ArrowRight className="h-4 w-4" />
          </button>
        </form>
      )}

      {error ? (
        <div
          className="mt-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-[13px] text-red-500"
          style={fontStyle}
        >
          {error}
        </div>
      ) : null}
    </div>
  );
}
