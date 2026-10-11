/** Placeholder block shown while data loads. Announced once through the surrounding role="status". */
export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-line ${className}`} aria-hidden="true" />;
}

export function TableSkeleton({ rows = 6, label }: { rows?: number; label: string }) {
  return (
    <div className="space-y-2 panel p-4" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-6 w-full" />
      ))}
    </div>
  );
}
