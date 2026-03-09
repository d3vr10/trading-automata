"use client";

const COLORS = [
  "oklch(0.75 0.18 160)",
  "oklch(0.65 0.20 280)",
  "oklch(0.70 0.16 45)",
  "oklch(0.60 0.22 310)",
  "oklch(0.72 0.15 200)",
  "oklch(0.68 0.14 120)",
];

interface AllocationBarProps {
  items: { label: string; value: number }[];
  height?: number;
  className?: string;
}

export function AllocationBar({ items, height = 8, className = "" }: AllocationBarProps) {
  const total = items.reduce((s, i) => s + Math.abs(i.value), 0);
  if (total === 0) return null;

  return (
    <div className={className}>
      <div className="flex rounded-full overflow-hidden" style={{ height }}>
        {items.map((item, i) => {
          const pct = (Math.abs(item.value) / total) * 100;
          return (
            <div
              key={item.label}
              style={{ width: `${pct}%`, background: COLORS[i % COLORS.length] }}
              title={`${item.label}: $${item.value.toFixed(2)} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {items.map((item, i) => (
          <div key={item.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-2 w-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
            <span>{item.label}</span>
            <span className="font-medium text-foreground/80">${item.value.toFixed(0)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
