function Skeleton({ className }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-[#F2F4F6] ${className ?? ""}`} />;
}

export default function ExtractLoading() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-96" />
      </div>
      <Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  );
}
