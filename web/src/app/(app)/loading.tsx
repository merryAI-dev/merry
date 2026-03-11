export default function AppLoading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#E5E8EB] border-t-[#191F28]" />
        <p className="text-sm text-[#8B95A1]">불러오는 중...</p>
      </div>
    </div>
  );
}
