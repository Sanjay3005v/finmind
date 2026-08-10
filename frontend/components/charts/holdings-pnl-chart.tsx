interface HoldingsPnlChartProps {
  data: { symbol: string; unrealized_pnl_percent: number }[];
}

const SCALE_CAP = 40;

/** Diverging per-holding P&L% — real, computed values only (see
 * app/financial/allocation.py::position_pnl on the backend). Bar length is
 * clamped to a ±40% visual scale so one outlier holding doesn't flatten
 * every other bar; the printed percentage is always the real, uncapped value. */
export function HoldingsPnlChart({ data }: HoldingsPnlChartProps) {
  const sorted = [...data].sort((a, b) => b.unrealized_pnl_percent - a.unrealized_pnl_percent);

  return (
    <div className="flex flex-col gap-2.5">
      {sorted.map((holding) => {
        const positive = holding.unrealized_pnl_percent >= 0;
        const magnitude = Math.min(Math.abs(holding.unrealized_pnl_percent), SCALE_CAP);
        const widthPercent = (magnitude / SCALE_CAP) * 50;

        return (
          <div key={holding.symbol} className="flex items-center gap-3 text-[13px]">
            <span className="w-24 shrink-0 truncate font-medium text-foreground">{holding.symbol}</span>
            <div className="relative h-4 flex-1">
              <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
              {positive ? (
                <div
                  className="absolute inset-y-0 left-1/2 rounded-r-sm bg-gain"
                  style={{ width: `${widthPercent}%` }}
                />
              ) : (
                <div
                  className="absolute inset-y-0 right-1/2 rounded-l-sm bg-loss"
                  style={{ width: `${widthPercent}%` }}
                />
              )}
            </div>
            <span
              className={
                "w-16 shrink-0 text-right tabular-nums " + (positive ? "text-gain" : "text-loss")
              }
            >
              {positive ? "+" : ""}
              {holding.unrealized_pnl_percent.toFixed(2)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
