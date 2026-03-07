function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#F2F4F6] ${className ?? ""}`} />;
}

export default function FundsLoading() {
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <Skeleton className="h-8 w-36" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-3 rounded-2xl border border-[#F2F4F6] p-5">
            <Skeleton className="h-5 w-40" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
            </div>
            <div className="flex items-center justify-between pt-2">
              <Skeleton className="h-6 w-20 rounded-full" />
              <Skeleton className="h-4 w-16" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
