interface SparklineProps {
  points: number[];
  width?: number;
  height?: number;
  className?: string;
}

/** Minimal inline trend line — real series only (equity curve / price
 * history points already computed elsewhere), never synthesized here. */
export function Sparkline({ points, width = 200, height = 44, className }: SparklineProps) {
  const clean = points.filter((p) => Number.isFinite(p));
  if (clean.length < 2) return null;

  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min || 1;
  const pad = 3;

  const coords = clean
    .map((value, i) => {
      const x = (i / (clean.length - 1)) * width;
      const y = height - pad - ((value - min) / span) * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const positive = clean[clean.length - 1] >= clean[0];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={className} preserveAspectRatio="none">
      <polyline
        points={coords}
        fill="none"
        stroke={positive ? "var(--gain)" : "var(--loss)"}
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
