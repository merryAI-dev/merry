import Link from "next/link";

export default function DiagnosisPage() {
  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-8">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#8A6F3E]">
            Diagnosis Studio
          </p>
          <h1
            className="mt-3 text-4xl font-black tracking-tight text-[#231F16]"
            style={{ fontFamily: "var(--font-merry-display, var(--font-korean))" }}
          >
            기업 현황을 진단하고 다음 작업을 준비합니다
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7 text-[#6C624D]">
            업로드, 진단 세션, 히스토리 공간을 분리해 두었습니다. 데이터 연결과 자동화는 다음 작업에서 이어 붙일 예정입니다.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              href: "/diagnosis/upload",
              eyebrow: "Upload",
              title: "시트를 올리고 전처리를 시작합니다",
            },
            {
              href: "/diagnosis/sessions",
              eyebrow: "Sessions",
              title: "진단 세션과 상태를 확인합니다",
            },
            {
              href: "/diagnosis/history",
              eyebrow: "History",
              title: "실행 기록과 후속 작업을 정리합니다",
            },
          ].map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="rounded-[28px] border border-[#E2D6BA] bg-[#FFF9EE] p-6 shadow-[0_18px_40px_rgba(52,40,18,0.08)] transition hover:-translate-y-0.5"
            >
              <div className="text-xs font-semibold uppercase tracking-[0.2em] text-[#A68645]">
                {item.eyebrow}
              </div>
              <div className="mt-3 text-xl font-black tracking-tight text-[#231F16]">{item.title}</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
