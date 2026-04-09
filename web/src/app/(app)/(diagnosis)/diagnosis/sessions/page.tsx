export default function DiagnosisSessionsPage() {
  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto max-w-4xl rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
        <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">
          Sessions
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">진단 세션 준비 중</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-[#6C624D]">
          진단 세션 목록, 상태, 후속 액션은 아직 비어 있습니다. 다음 작업에서 저장소와 API를 붙여 실제 세션 보드를 연결합니다.
        </p>
      </div>
    </div>
  );
}
