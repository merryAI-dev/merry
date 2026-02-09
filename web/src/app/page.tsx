"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Shield } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";

const TEAM_OPTIONS = [
  { label: "Team 1", value: "team_1" },
  { label: "Team 2", value: "team_2" },
  { label: "Team 3", value: "team_3" },
  { label: "Team 4", value: "team_4" },
];

export default function Home() {
  const router = useRouter();
  const [teamId, setTeamId] = React.useState("team_1");
  const [memberName, setMemberName] = React.useState("");
  const [passcode, setPasscode] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  async function login(e: React.FormEvent) {
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
      setError("로그인 요청에 실패했습니다. 네트워크/서버 설정을 확인하세요.");
    } finally {
      setBusy(false);
    }
  }

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

        <Card variant="strong" className="p-6 md:p-7">
          <div className="text-sm font-medium text-[color:var(--ink)]">
            팀 워크스페이스 로그인
          </div>
          <div className="mt-1 text-sm text-[color:var(--muted)]">
            Vercel 환경변수로 팀 코드를 설정하고, AWS(DynamoDB/S3)에 히스토리를 저장합니다.
          </div>

          <form className="mt-6 space-y-3" onSubmit={login}>
            <label className="block">
              <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">
                팀
              </div>
              <select
                className="h-11 w-full rounded-xl border border-[color:var(--line)] bg-white/80 px-3 text-sm text-[color:var(--ink)] outline-none focus:border-[color:var(--accent)]"
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
              <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">
                닉네임
              </div>
              <Input
                value={memberName}
                onChange={(e) => setMemberName(e.target.value)}
                placeholder="이름 또는 닉네임"
                autoComplete="name"
              />
            </label>

            <label className="block">
              <div className="mb-1 text-xs font-medium text-[color:var(--muted)]">
                팀 코드
              </div>
              <Input
                value={passcode}
                onChange={(e) => setPasscode(e.target.value)}
                placeholder="워크스페이스 코드"
                type="password"
                autoComplete="current-password"
              />
            </label>

            {error ? (
              <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-900">
                {error}
              </div>
            ) : null}

            <Button
              variant="primary"
              className="w-full"
              disabled={busy || !memberName || !passcode}
              type="submit"
            >
              워크스페이스 들어가기 <ArrowRight className="h-4 w-4" />
            </Button>

            <div className="text-xs leading-5 text-[color:var(--muted)]">
              환경변수 필요:{" "}
              <span className="font-mono">AWS_REGION</span>,{" "}
              <span className="font-mono">MERRY_DDB_TABLE</span>,{" "}
              <span className="font-mono">MERRY_S3_BUCKET</span>,{" "}
              <span className="font-mono">MERRY_SQS_QUEUE_URL</span>,{" "}
              <span className="font-mono">WORKSPACE_JWT_SECRET</span>,{" "}
              <span className="font-mono">WORKSPACE_CODE</span>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
