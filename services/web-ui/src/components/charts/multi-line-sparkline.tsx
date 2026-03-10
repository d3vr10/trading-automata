"use client";

import { useId } from "react";

interface Series {
  label: string;
  data: number[];
  color?: string;
}

interface MultiLineSparklineProps {
  series: Series[];
  width?: number;
  height?: number;
  className?: string;
  strokeWidth?: number;
}

const PALETTE = [
  "oklch(0.75 0.18 160)", // green
  "oklch(0.7 0.15 250)",  // blue
  "oklch(0.7 0.18 40)",   // orange
  "oklch(0.65 0.2 320)",  // purple
  "oklch(0.75 0.15 80)",  // yellow
  "oklch(0.65 0.22 0)",   // red
];

export function MultiLineSparkline({
  series,
  width = 800,
  height = 120,
  className = "",
  strokeWidth = 1.5,
}: MultiLineSparklineProps) {
  const baseId = useId();
  const pad = 4;

  if (series.length === 0) return null;

  // Global min/max across all series
  let globalMin = Infinity;
  let globalMax = -Infinity;
  for (const s of series) {
    for (const v of s.data) {
      if (v < globalMin) globalMin = v;
      if (v > globalMax) globalMax = v;
    }
  }
  const range = globalMax - globalMin || 1;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        {series.map((s, idx) => {
          const color = s.color || PALETTE[idx % PALETTE.length];
          return (
            <linearGradient key={`${baseId}-g-${idx}`} id={`${baseId}-g-${idx}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.12} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          );
        })}
      </defs>
      {series.map((s, idx) => {
        if (s.data.length < 2) return null;
        const color = s.color || PALETTE[idx % PALETTE.length];
        const points = s.data.map((v, i) => {
          const x = pad + (i / (s.data.length - 1)) * (width - pad * 2);
          const y = pad + (1 - (v - globalMin) / range) * (height - pad * 2);
          return `${x.toFixed(1)},${y.toFixed(1)}`;
        });
        const linePath = `M${points.join(" L")}`;
        const fillPath = `${linePath} L${(width - pad).toFixed(1)},${(height - pad).toFixed(1)} L${pad},${(height - pad).toFixed(1)} Z`;
        return (
          <g key={idx}>
            <path d={fillPath} fill={`url(#${baseId}-g-${idx})`} />
            <path d={linePath} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
          </g>
        );
      })}
    </svg>
  );
}

export function MultiLineSparklineLegend({ series }: { series: Series[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1">
      {series.map((s, idx) => (
        <div key={s.label} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className="h-2 w-2 rounded-full shrink-0"
            style={{ backgroundColor: s.color || PALETTE[idx % PALETTE.length] }}
          />
          {s.label}
        </div>
      ))}
    </div>
  );
}
