import type { AllocationSlice } from "@/lib/api/types";

const STEP_COLORS = [
  "var(--accent-500)",
  "var(--accent-600)",
  "var(--accent-700)",
  "var(--chart-5)",
  "var(--accent-400)",
];

interface SectorBarsProps {
  data: AllocationSlice[];
}

/** Labelled progress bars for a percentage breakdown — real allocation
 * percentages only (app/financial/allocation.py on the backend). */
export function SectorBars({ data }: SectorBarsProps) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0);
  const sorted = [...data].sort((a, b) => b.value - a.value);

  return (
    <div className="flex flex-col gap-3">
      {sorted.map((slice, index) => {
        const percent = total ? (slice.value / total) * 100 : 0;
        return (
          <div key={slice.label}>
            <div className="mb-1.5 flex items-center gap-3 text-[13px]">
              <span className="min-w-0 truncate text-foreground">{slice.label}</span>
              <span className="ml-auto shrink-0 tabular-nums text-muted-foreground">{percent.toFixed(1)}%</span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--neutral-900)]">
              <div
                className="h-full rounded-full"
                style={{ width: `${percent}%`, background: STEP_COLORS[index % STEP_COLORS.length] }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
