"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import type { AllocationSlice } from "@/lib/api/types";
import { formatCurrency } from "@/lib/format";
import { cn } from "@/lib/utils";

const SLICE_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

interface AllocationDonutChartProps {
  data: AllocationSlice[];
  className?: string;
  /** When provided, the legend shows the real amount alongside the percent. */
  currency?: string;
}

/**
 * Categorical donut with a text legend beside it — the light-mode palette
 * has a contrast WARN against the chart surface for a few slots, so labels
 * are always visible rather than relying on hue alone (dataviz relief rule).
 * Sized off the CARD's own width (container query), not the viewport — this
 * chart renders inside cards of very different widths (a narrow dashboard
 * sidebar stack vs. a wide portfolio-detail column).
 */
export function AllocationDonutChart({ data, className, currency }: AllocationDonutChartProps) {
  const total = data.reduce((sum, slice) => sum + slice.value, 0);

  return (
    <div className={cn("@container", className)}>
      <div className="flex flex-col gap-4 @sm:flex-row @sm:items-center">
        <div className="h-36 w-36 shrink-0 self-center @sm:h-40 @sm:w-40 @sm:self-auto">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="label"
                innerRadius="62%"
                outerRadius="100%"
                paddingAngle={2}
                stroke="var(--card)"
                strokeWidth={2}
              >
                {data.map((entry, index) => (
                  <Cell key={entry.label} fill={SLICE_COLORS[index % SLICE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: "var(--popover)",
                  color: "var(--popover-foreground)",
                  border: "1px solid var(--border)",
                  borderRadius: "var(--radius-md)",
                  fontSize: 12,
                }}
                formatter={(value, name) => {
                  const numericValue = Number(value);
                  const percent = total ? ((numericValue / total) * 100).toFixed(1) : "0";
                  return [`${numericValue.toLocaleString()} (${percent}%)`, String(name)];
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="flex min-w-0 flex-1 flex-col gap-2 text-sm">
          {data.map((slice, index) => (
            <li key={slice.label} className="flex items-center gap-3">
              <span className="flex min-w-0 items-center gap-2 text-foreground">
                <span
                  className="size-2.5 shrink-0 rounded-full"
                  style={{ background: SLICE_COLORS[index % SLICE_COLORS.length] }}
                  aria-hidden
                />
                <span className="truncate">{slice.label}</span>
              </span>
              <span className="ml-auto flex shrink-0 items-baseline gap-2 tabular-nums text-muted-foreground">
                {currency && <span className="text-foreground">{formatCurrency(slice.value, currency)}</span>}
                <span className="font-medium">
                  {total ? ((slice.value / total) * 100).toFixed(1) : "0.0"}%
                </span>
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
