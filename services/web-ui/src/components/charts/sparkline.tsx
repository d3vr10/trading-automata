"use client";

import { useId } from "react";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  fillOpacity?: number;
  strokeWidth?: number;
  className?: string;
}

function minMax(data: number[]): [number, number] {
  let min = data[0];
  let max = data[0];
  for (let i = 1; i < data.length; i++) {
    if (data[i] < min) min = data[i];
    if (data[i] > max) max = data[i];
  }
  return [min, max];
}

export function Sparkline({
  data,
  width = 200,
  height = 48,
  color = "oklch(0.75 0.18 160)",
  fillOpacity = 0.15,
  strokeWidth = 1.5,
  className = "",
}: SparklineProps) {
  const gradId = useId();

  if (data.length < 2) {
    return (
      <svg width={width} height={height} className={className}>
        <line
          x1={0} y1={height / 2} x2={width} y2={height / 2}
          stroke={color} strokeWidth={strokeWidth} strokeDasharray="4 4" opacity={0.3}
        />
      </svg>
    );
  }

  const pad = 2;
  const [min, max] = minMax(data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (width - pad * 2);
    const y = pad + (1 - (v - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const linePath = `M${points.join(" L")}`;
  const fillPath = `${linePath} L${(width - pad).toFixed(1)},${(height - pad).toFixed(1)} L${pad},${(height - pad).toFixed(1)} Z`;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={fillOpacity} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={fillPath} fill={`url(#${gradId})`} />
      <path d={linePath} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
