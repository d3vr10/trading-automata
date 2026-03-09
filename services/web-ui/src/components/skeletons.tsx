import { Skeleton } from "@/components/ui/skeleton";

export function CardSkeleton() {
  return (
    <div className="glass rounded-2xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24 bg-accent/60" />
        <Skeleton className="h-8 w-8 rounded-xl bg-accent/60" />
      </div>
      <Skeleton className="h-8 w-32 bg-accent/60" />
      <Skeleton className="h-3 w-20 bg-accent/40" />
    </div>
  );
}

export function ChartSkeleton({ height = 120 }: { height?: number }) {
  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
        <Skeleton className="h-5 w-28 bg-accent/60" />
        <Skeleton className="h-4 w-16 bg-accent/40" />
      </div>
      <div className="p-5">
        <Skeleton className={`w-full bg-accent/40 rounded-lg`} style={{ height }} />
      </div>
    </div>
  );
}

export function ListCardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border/30 flex items-center justify-between">
        <Skeleton className="h-5 w-28 bg-accent/60" />
        <Skeleton className="h-3 w-14 bg-accent/40" />
      </div>
      <div className="p-5 space-y-2">
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="flex items-center justify-between rounded-xl glass-subtle p-3">
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-24 bg-accent/60" />
              <Skeleton className="h-3 w-16 bg-accent/40" />
            </div>
            <Skeleton className="h-5 w-16 rounded-full bg-accent/50" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function BotCardSkeleton() {
  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-border/30">
        <Skeleton className="h-5 w-28 bg-accent/60" />
        <Skeleton className="h-5 w-16 rounded-full bg-accent/50" />
      </div>
      <div className="p-5 space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-14 bg-accent/40" />
              <Skeleton className="h-4 w-20 bg-accent/60" />
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-16 rounded-lg bg-accent/50" />
          <Skeleton className="h-8 w-16 rounded-lg bg-accent/50" />
        </div>
      </div>
    </div>
  );
}

export function TableSkeleton({ columns, rows = 5 }: { columns: number; rows?: number }) {
  return (
    <>
      {Array.from({ length: rows }, (_, i) => (
        <tr key={i} className="border-border/20">
          {Array.from({ length: columns }, (_, j) => (
            <td key={j} className="p-4">
              <Skeleton className={`h-4 bg-accent/50 ${j === 0 ? "w-20" : j === columns - 1 ? "w-16" : "w-14"}`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

export function StatusCardSkeleton() {
  return (
    <div className="glass rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-border/30">
        <Skeleton className="h-5 w-20 bg-accent/60" />
      </div>
      <div className="p-5 space-y-5">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="glass-subtle rounded-xl p-3 space-y-2">
              <Skeleton className="h-3 w-16 bg-accent/40" />
              <Skeleton className="h-4 w-20 bg-accent/60" />
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <Skeleton className="h-8 w-16 rounded-lg bg-accent/50" />
          <Skeleton className="h-8 w-16 rounded-lg bg-accent/50" />
        </div>
      </div>
    </div>
  );
}

export function CredentialSkeleton() {
  return (
    <div className="glass rounded-2xl flex items-center justify-between p-5">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10 rounded-xl bg-accent/50" />
        <div className="space-y-1.5">
          <Skeleton className="h-4 w-32 bg-accent/60" />
          <Skeleton className="h-3 w-20 bg-accent/40" />
        </div>
      </div>
      <div className="flex items-center gap-3">
        <Skeleton className="h-5 w-24 rounded-full bg-accent/40" />
        <Skeleton className="h-8 w-8 rounded-lg bg-accent/50" />
      </div>
    </div>
  );
}

export function StrategyCardSkeleton() {
  return (
    <div className="glass rounded-2xl overflow-hidden flex flex-col">
      <div className="px-5 pt-5 pb-3 flex items-start justify-between">
        <div className="flex-1 min-w-0 space-y-2">
          <Skeleton className="h-5 w-32 bg-accent/60" />
          <Skeleton className="h-3 w-48 bg-accent/40" />
        </div>
        <Skeleton className="h-[52px] w-[52px] rounded-full bg-accent/50 shrink-0" />
      </div>
      <div className="px-5 flex gap-1.5">
        <Skeleton className="h-5 w-20 rounded-full bg-accent/40" />
        <Skeleton className="h-5 w-16 rounded-full bg-accent/40" />
        <Skeleton className="h-5 w-12 rounded-full bg-accent/40" />
      </div>
      <div className="px-5 mt-3">
        <Skeleton className="h-3 w-full bg-accent/30" />
      </div>
      <div className="mt-auto px-5 py-3 border-t border-border/20 flex items-center gap-4">
        <Skeleton className="h-3 w-8 bg-accent/40" />
        <Skeleton className="h-3 w-20 bg-accent/40" />
        <Skeleton className="h-3 w-14 bg-accent/40 ml-auto" />
      </div>
      <div className="px-5 pb-4 flex gap-1">
        <Skeleton className="h-4 w-12 rounded bg-accent/30" />
        <Skeleton className="h-4 w-10 rounded bg-accent/30" />
      </div>
    </div>
  );
}
