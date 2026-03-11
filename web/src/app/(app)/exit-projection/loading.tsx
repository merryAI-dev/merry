function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#F2F4F6] ${className ?? ""}`} />;
}

export default function ExitProjectionLoading() {
  return (
    <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
      <Skeleton className="h-8 w-52" />

      {/* Input form skeleton */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
        ))}
      </div>

      {/* Chart placeholder */}
      <Skeleton className="h-64 w-full rounded-2xl" />

      {/* Table placeholder */}
      <div className="space-y-2">
        <Skeleton className="h-8 w-full rounded-lg" />
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-10 w-full rounded-lg" />
        ))}
      </div>
    </div>
  );
}
