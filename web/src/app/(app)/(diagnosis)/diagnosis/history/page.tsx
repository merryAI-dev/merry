/* eslint-disable @next/next/no-img-element */
"use client";

import * as React from "react";
import { History, Loader2, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/Button";
import { apiFetch } from "@/lib/apiClient";

type DiagnosisEvent = {
  eventId: string;
  sessionId: string;
  sessionTitle?: string;
  type: string;
  actor: string;
  createdAt: string;
  description: string;
};

export default function DiagnosisHistoryPage() {
  const [events, setEvents] = React.useState<DiagnosisEvent[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  const load = React.useCallback(async () => {
    setError(null);
    try {
      const result = await apiFetch<{ events: DiagnosisEvent[] }>("/api/diagnosis/history?limit=30");
      setEvents(result.events ?? []);
    } catch {
      setError("진단 히스토리를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto max-w-5xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">History</div>
            <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">진단 실행 히스토리</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#6C624D]">
              diagnosis 전용 세션 생성, 업로드, 실행 시작, 완료/실패 이벤트를 시간순으로 확인합니다.
            </p>
          </div>
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            새로고침
          </Button>
        </div>

        {error ? (
          <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        ) : null}

        <div className="mt-8 grid gap-4">
          {events.map((event) => (
            <article
              key={event.eventId}
              className="rounded-[28px] border border-[#E2D6BA] bg-[#FFF9EE] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.08)]"
            >
              <div className="flex items-start gap-3">
                <div className="rounded-2xl bg-[#F7EED9] p-3 text-[#A68645]">
                  <History className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">
                    {event.type}
                  </div>
                  <h2 className="mt-2 text-xl font-black tracking-tight text-[#231F16]">
                    {event.sessionTitle || event.sessionId}
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-[#6C624D]">{event.description}</p>
                </div>
              </div>
            </article>
          ))}
          {!loading && events.length === 0 ? (
            <div className="rounded-[28px] border border-dashed border-[#D8C59A] bg-[#FFFCF5] px-6 py-10 text-center text-sm text-[#7C6E55]">
              아직 기록된 diagnosis 이벤트가 없습니다.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
