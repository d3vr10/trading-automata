"use client";

interface MiniBarChartProps {
  data: { label: string; value: number }[];
  width?: number;
  height?: number;
  positiveColor?: string;
  negativeColor?: string;
  className?: string;
}

export function MiniBarChart({
  data,
  width = 300,
  height = 80,
  positiveColor = "oklch(0.75 0.18 160)",
  negativeColor = "oklch(0.65 0.22 25)",
  className = "",
}: MiniBarChartProps) {
  if (data.length === 0) return null;

  let maxAbs = 0.01;
  for (const d of data) {
    const abs = Math.abs(d.value);
    if (abs > maxAbs) maxAbs = abs;
  }
  const barWidth = Math.max(2, (width - data.length * 2) / data.length);
  const mid = height / 2;

  return (
    <svg width={width} height={height} className={className} viewBox={`0 0 ${width} ${height}`}>
      {/* zero line */}
      <line x1={0} y1={mid} x2={width} y2={mid} stroke="oklch(0.4 0.03 280)" strokeWidth={0.5} />
      {data.map((d, i) => {
        const barH = (Math.abs(d.value) / maxAbs) * (mid - 4);
        const x = i * (barWidth + 2) + 1;
        const y = d.value >= 0 ? mid - barH : mid;
        const color = d.value >= 0 ? positiveColor : negativeColor;
        return (
          <rect
            key={i}
            x={x} y={y}
            width={barWidth} height={Math.max(1, barH)}
            rx={1}
            fill={color}
            opacity={0.85}
          >
            <title>{`${d.label}: ${d.value >= 0 ? "+" : ""}${d.value.toFixed(2)}`}</title>
          </rect>
        );
      })}
    </svg>
  );
}
