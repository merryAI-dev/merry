export default function DiagnosisUploadPage() {
  return (
    <div className="min-h-full px-6 py-10 md:px-10">
      <div className="mx-auto max-w-4xl rounded-[32px] border border-[#E2D6BA] bg-[#FFF9EE] p-8 shadow-[0_18px_40px_rgba(52,40,18,0.08)]">
        <div className="text-sm font-semibold uppercase tracking-[0.22em] text-[#A68645]">
          Upload
        </div>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-[#231F16]">업로드 준비 중</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-[#6C624D]">
          진단용 엑셀 업로드 플로우와 파일 검증은 아직 연결되지 않았습니다. 이 화면은 Task 2에서 진단 제품 셸을 고정하기 위한 자리입니다.
        </p>
      </div>
    </div>
  );
}
