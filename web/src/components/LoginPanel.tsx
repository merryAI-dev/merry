"use client";

import * as React from "react";
import { ArrowRight, Loader2, ShieldCheck } from "lucide-react";
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

function DarkInput({
  label,
  ...props
}: { label: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = React.useState(false);
  return (
    <div>
      <label
        className="block text-xs font-medium mb-1.5"
        style={{ color: "var(--ink-light)" }}
      >
        {label}
      </label>
      <input
        {...props}
        onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
        onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
        className="w-full h-11 rounded-xl px-3 text-sm outline-none transition-all duration-150"
        style={{
          background: "rgba(255,255,255,0.04)",
          border: `1px solid ${focused ? "rgba(124,58,237,0.6)" : "rgba(255,255,255,0.08)"}`,
          boxShadow: focused ? "0 0 0 3px rgba(124,58,237,0.15)" : "none",
          color: "var(--ink)",
          fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)",
        }}
      />
    </div>
  );
}

function DarkSelect({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { label: string; value: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  const [focused, setFocused] = React.useState(false);
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--ink-light)" }}>
        {label}
      </label>
      <select
        className="w-full h-11 rounded-xl px-3 text-sm outline-none transition-all duration-150 appearance-none"
        style={{
          background: "rgba(255,255,255,0.04)",
          border: `1px solid ${focused ? "rgba(124,58,237,0.6)" : "rgba(255,255,255,0.08)"}`,
          boxShadow: focused ? "0 0 0 3px rgba(124,58,237,0.15)" : "none",
          color: "var(--ink)",
          fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)",
        }}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} style={{ background: "#1A1A24" }}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
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

  return (
    <div
      className="w-full rounded-2xl p-6"
      style={{
        background: "rgba(17,17,24,0.8)",
        border: "1px solid rgba(255,255,255,0.08)",
        backdropFilter: "blur(20px)",
        boxShadow: "0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(124,58,237,0.06) inset",
        fontFamily: "var(--font-korean, var(--font-merry-sans), system-ui)",
      }}
    >
      {/* Card header */}
      <div className="mb-5">
        <p
          className="text-sm font-semibold mb-1"
          style={{ color: "var(--ink)" }}
        >
          워크스페이스 로그인
        </p>
        <p className="text-xs" style={{ color: "var(--ink-light)" }}>
          {googleEnabled ? "회사 Google 계정으로 로그인합니다." : "팀 코드로 로그인하세요."}
        </p>
      </div>

      {googleEnabled ? (
        <>
          <button
            onClick={loginWithGoogle}
            className="w-full h-12 rounded-xl font-semibold text-sm flex items-center justify-center gap-2.5 transition-all duration-150 active:scale-[0.98]"
            style={{
              background: "linear-gradient(135deg, #7C3AED, #6D28D9)",
              color: "#fff",
              boxShadow: "0 2px 20px rgba(124,58,237,0.45)",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.boxShadow = "0 4px 28px rgba(124,58,237,0.6)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.boxShadow = "0 2px 20px rgba(124,58,237,0.45)";
            }}
          >
            <GoogleIcon />
            Google로 로그인
          </button>
        </>
      ) : (
        <form className="space-y-3" onSubmit={loginWithPasscode}>
          <DarkSelect
            label="팀"
            options={TEAM_OPTIONS}
            value={teamId}
            onChange={setTeamId}
          />
          <DarkInput
            label="닉네임"
            value={memberName}
            onChange={(e) => setMemberName(e.target.value)}
            placeholder="이름 또는 닉네임"
            autoComplete="name"
          />
          <DarkInput
            label="팀 코드"
            value={passcode}
            onChange={(e) => setPasscode(e.target.value)}
            placeholder="워크스페이스 코드"
            type="password"
            autoComplete="current-password"
          />

          <button
            type="submit"
            disabled={busy || !memberName || !passcode}
            className="w-full h-12 mt-1 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 transition-all duration-150 active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none"
            style={{
              background: "linear-gradient(135deg, #7C3AED, #6D28D9)",
              color: "#fff",
              boxShadow: "0 2px 20px rgba(124,58,237,0.35)",
            }}
          >
            {busy ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                워크스페이스 들어가기
                <ArrowRight className="h-4 w-4" />
              </>
            )}
          </button>
        </form>
      )}

      {error && (
        <div
          className="mt-4 rounded-xl px-4 py-3 text-xs"
          style={{
            background: "rgba(244,63,94,0.08)",
            border: "1px solid rgba(244,63,94,0.2)",
            color: "#FB7185",
          }}
        >
          {error}
        </div>
      )}
    </div>
  );
}
