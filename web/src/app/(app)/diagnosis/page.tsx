import Link from "next/link";

export default function DiagnosisPage() {
  return (
    <div className="min-h-full px-6 py-12 md:px-10">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.22em]" style={{ color: "#6F7780" }}>
            현황진단
          </p>
          <h1
            className="mt-3 text-4xl font-black tracking-tight text-[#1A1D21]"
            style={{ fontFamily: "var(--font-merry-display, var(--font-korean))" }}
          >
            현황진단 준비 중
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-7" style={{ color: "#6F7780" }}>
            곧 진단 전용 작업 공간으로 이어질 예정입니다. 지금은 제품 선택 화면에서 다시 이동할 수 있습니다.
          </p>
        </div>

        <Link
          href="/products"
          className="inline-flex w-fit items-center rounded-xl border border-[#E3E5E8] bg-white px-4 py-2.5 text-sm font-semibold text-[#1A1D21] shadow-sm transition hover:-translate-y-0.5"
        >
          제품 선택으로 돌아가기
        </Link>
      </div>
    </div>
  );
}
